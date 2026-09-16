"""Extraction, candidate linkage and conservative one-to-one match decisions.

Only evaluate() reads ground truth. Scores are transparent heuristics, not
probabilities; default settings are illustrative, not estimated from test labels.
"""
import csv
import hashlib
import math
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

THRESHOLD = .86
MARGIN = .08
RECORD_FIELDS = ["record_id", "year", "town", "name_raw", "given", "surname", "birth",
                 "role", "address", "source_file", "source_line", "source_sha256", "raw_text", "quality_flags"]
CANDIDATE_FIELDS = ["left_id", "right_id", "town", "surname_similarity", "given_similarity",
                    "birth_agreement", "role_similarity", "address_similarity", "score"]
DECISION_FIELDS = ["left_id", "town", "status", "right_id", "best_candidate_id", "score",
                   "margin", "reverse_margin", "reason"]
ISSUE_FIELDS = ["source_file", "source_line", "source_sha256", "raw_text", "reason"]


def normalise(value):
    value = value.casefold().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    value = "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", value).split())


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fields):
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def extract(pages):
    """Parse two documented transcription layouts; preserve failures and provenance.

    This starts from OCR-like text, not images. Unknown page metadata fails closed;
    unparseable body lines are retained in a rejection table, never silently dropped.
    """
    records, issues = [], []
    files = sorted(Path(pages).glob("*.txt"))
    if not files:
        raise ValueError("No source pages found")
    patterns = {
        1920: r"\d+\s*\|\s*(.*?)\s*\|\s*b\.\s*([^|]+)\|\s*([^|]+)\|\s*(.*)",
        1930: r"\d+\.\s*(.*?)\s*;\s*born\s*([^;]+);\s*role=([^;]+);\s*addr=(.*)",
    }
    for file in files:
        raw = file.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        lines = raw.decode("utf-8").splitlines()
        if len(lines) < 4 or not lines[1].startswith("Municipality: ") or not lines[2].startswith("Year: "):
            raise ValueError(f"Invalid page metadata: {file.name}")
        town, year = lines[1].split(": ", 1)[1], int(lines[2].split(": ", 1)[1])
        if not town.strip() or year not in patterns:
            raise ValueError(f"Unsupported town/year: {file.name}")
        for line_number, line in enumerate(lines[4:], 5):
            if not line.strip():
                continue
            source = dict(source_file=file.name, source_line=line_number, source_sha256=digest, raw_text=line)
            match = re.fullmatch(patterns[year], line.strip())
            if not match:
                issues.append(dict(source, reason="unrecognised_row_layout"))
                continue
            name, birth, role, address = [x.strip() for x in match.groups()]
            if year == 1920 and name.count(",") == 1:
                surname, given = [x.strip() for x in name.split(",")]
            elif year == 1930 and len(name.split()) == 2:
                given, surname = name.split()
            else:
                issues.append(dict(source, reason="unsupported_name_structure"))
                continue
            if not normalise(given) or not normalise(surname):
                issues.append(dict(source, reason="missing_name"))
                continue
            birth = "" if birth == "?" else birth
            if birth and (not re.fullmatch(r"\d{4}", birth) or not year - 100 <= int(birth) <= year - 16):
                issues.append(dict(source, reason="invalid_birth_year"))
                continue
            flags = []
            if not birth:
                flags.append("missing_birth")
            if len(normalise(given)) == 1:
                flags.append("given_initial")
            if address == "?":
                address = ""
                flags.append("missing_address")
            records.append(dict(source, record_id=f"{file.stem}:L{line_number:03d}", year=year, town=town,
                                name_raw=name, given=normalise(given), surname=normalise(surname),
                                birth=birth, role=normalise(role), address=normalise(address),
                                quality_flags="|".join(flags)))
    validate_records(records)
    return records, issues


def validate_records(records):
    seen = set()
    for row in records:
        if set(RECORD_FIELDS) - row.keys():
            raise ValueError("Incomplete record schema")
        if not row["record_id"] or row["record_id"] in seen:
            raise ValueError("Empty or duplicate record ID")
        seen.add(row["record_id"])
        if int(row["year"]) not in (1920, 1930) or not row["town"] or not row["surname"] or not row["given"]:
            raise ValueError("Invalid record year, town or name")


def similarity(left, right):
    # Missing evidence contributes zero; it is not interpreted as disagreement.
    return SequenceMatcher(None, left, right, autojunk=False).ratio() if left and right else 0.


def score_pair(left, right):
    given = similarity(left["given"], right["given"])
    if left["given"][0] == right["given"][0] and min(len(left["given"]), len(right["given"])) == 1:
        given = .65  # An initial is weaker evidence than a complete first name.
    parts = dict(surname_similarity=similarity(left["surname"], right["surname"]),
                 given_similarity=given,
                 birth_agreement=int(bool(left["birth"]) and left["birth"] == right["birth"]),
                 role_similarity=similarity(left["role"], right["role"]),
                 address_similarity=similarity(left["address"], right["address"]))
    score = sum(parts[key] * weight for key, weight in zip(parts, (.45, .25, .20, .05, .05)))
    return dict(parts, score=round(score, 6))


def candidates(records, same_town=True):
    """Block by town (optional), then retain surname similarity >= .55.

    ponytail: quadratic comparisons suit this 320-record demo; use indexed
    blocking for a large register instead of scaling the all-pairs exercise.
    """
    validate_records(records)
    left = [r for r in records if int(r["year"]) == 1920]
    right = [r for r in records if int(r["year"]) == 1930]
    result = []
    for a in left:
        for b in right:
            if same_town and a["town"] != b["town"]:
                continue
            parts = score_pair(a, b)
            if parts["surname_similarity"] >= .55:
                result.append(dict(left_id=a["record_id"], right_id=b["record_id"], town=a["town"], **parts))
    return result


def find_matches(records, pairs, threshold=THRESHOLD, margin=MARGIN):
    """Accept only mutual first choices with sufficient score and both margins.

    This deliberately abstains rather than forcing a global one-to-one assignment.
    No truth labels enter this function; ties remain review cases even at margin=0.
    """
    validate_records(records)
    if not all(math.isfinite(x) and 0 <= x <= 1 for x in (threshold, margin)):
        raise ValueError("Threshold and margin must be finite numbers in [0, 1]")
    left_ids = {r["record_id"] for r in records if int(r["year"]) == 1920}
    right_ids = {r["record_id"] for r in records if int(r["year"]) == 1930}
    forward, reverse, seen = defaultdict(list), defaultdict(list), set()
    for pair in pairs:
        key = pair["left_id"], pair["right_id"]
        if key in seen or key[0] not in left_ids or key[1] not in right_ids:
            raise ValueError("Duplicate candidate pair or unknown source identity")
        if not math.isfinite(float(pair["score"])) or not 0 <= float(pair["score"]) <= 1:
            raise ValueError("Invalid candidate score")
        seen.add(key)
        forward[key[0]].append(pair)
        reverse[key[1]].append(pair)
    for groups in (forward, reverse):
        for values in groups.values():
            values.sort(key=lambda p: (-float(p["score"]), p["left_id"], p["right_id"]))
    def gap(values):
        return float(values[0]["score"]) - (float(values[1]["score"]) if len(values) > 1 else 0.)
    decisions = []
    for left in (r for r in records if int(r["year"]) == 1920):
        options = forward[left["record_id"]]
        row = dict(left_id=left["record_id"], town=left["town"], status="unmatched", right_id="",
                   best_candidate_id="", score="", margin="", reverse_margin="", reason="no_candidates")
        if options:
            best = options[0]
            rivals = reverse[best["right_id"]]
            forward_gap, reverse_gap = gap(options), gap(rivals)
            row.update(best_candidate_id=best["right_id"], score=float(best["score"]),
                       margin=round(forward_gap, 6), reverse_margin=round(reverse_gap, 6))
            if float(best["score"]) < threshold:
                row.update(status="review" if float(best["score"]) >= .55 else "unmatched", reason="below_threshold")
            elif forward_gap <= 1e-12 or forward_gap + 1e-12 < margin:
                row.update(status="review", reason="ambiguous_source")
            elif rivals[0]["left_id"] != left["record_id"] or reverse_gap <= 1e-12 or reverse_gap + 1e-12 < margin:
                row.update(status="review", reason="contested_target")
            else:
                row.update(status="accepted", right_id=best["right_id"], reason="mutual_best_with_margin")
        decisions.append(row)
    accepted = [r["right_id"] for r in decisions if r["status"] == "accepted"]
    assert len(accepted) == len(set(accepted)), "Target assigned twice"
    return decisions


def evaluate(decisions, pairs, truth):
    """Evaluate ALL baseline identities, including movers, rejects and abstentions.

    Recall denominator: all true continuers, not just those inside candidate blocks.
    Coverage denominator: all baseline people. Undefined rates remain None.
    """
    truth_map = {r["left_id"]: r["right_id"] for r in truth}
    if len(truth_map) != len(truth) or "" in truth_map:
        raise ValueError("Duplicate or empty truth identity")
    decisions_map = {r["left_id"]: r for r in decisions}
    if len(decisions_map) != len(decisions) or "" in decisions_map:
        raise ValueError("Duplicate or empty decision identity")
    if set(truth_map) - decisions_map.keys():
        raise ValueError("Evaluation has missing baseline decisions")
    real_pairs = {(left, right) for left, right in truth_map.items() if right}
    candidate_pairs = {(r["left_id"], r["right_id"]) for r in pairs}
    accepted = {(r["left_id"], r["right_id"]) for r in decisions
                if r["status"] == "accepted" and r["left_id"] in truth_map}
    correct = len(accepted & real_pairs)
    counts = Counter(decisions_map[key]["status"] for key in truth_map)
    ratio = lambda num, den: num / den if den else None
    return dict(baseline=len(truth_map), true_links=len(real_pairs), accepted=len(accepted),
                correct=correct, false_links=len(accepted) - correct, review=counts["review"],
                unmatched=counts["unmatched"], precision=ratio(correct, len(accepted)),
                recall=ratio(correct, len(real_pairs)), coverage=ratio(len(accepted), len(truth_map)),
                candidate_recall=ratio(len(real_pairs & candidate_pairs), len(real_pairs)))


def threshold_sweep(records, pairs, development_truth):
    return [dict(threshold=t, **evaluate(find_matches(records, pairs, t), pairs, development_truth))
            for t in (.55, .60, .65, .70, .75, .80, .86, .90, .95, 1.)]
