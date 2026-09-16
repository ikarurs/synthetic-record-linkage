"""Create fictional OCR-like registers and separate evaluation truth; no external data."""
import csv
import random
from pathlib import Path

TOWNS = ("Auenfels", "Birkenhafen", "Eichenried", "Falkenbrueck",
         "Lindenfurt", "Sonnenried", "Tannenhafen", "Wiesenfels")
GIVEN = ("Anna", "Emil", "Frieda", "Otto", "Helene", "Karl", "Marta", "Paul",
         "Luise", "Ernst", "Clara", "Fritz", "Ida", "Max", "Elise", "Walter")
SURNAMES = ("Müller", "Schmidt", "Meyer", "Weber", "Fischer", "Wagner", "Becker",
            "Hoffmann", "Schäfer", "Koch", "Bauer", "Richter", "Klein", "Wolf")
ROLES = ("clerk", "registrar", "engineer", "inspector", "archivist")


def make_dataset(destination, seed=20260916):
    """Write two registers per town. Truth IDs identify lines, never name features.

    Per town: 20 people at baseline; 16 persist (14 local, 2 move), 4 leave,
    and 4 entrants appear. Movers stay inside their four-town evaluation split.
    Two different people per town deliberately share the same observed details.
    """
    destination = Path(destination)
    pages = destination / "pages"
    pages.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    early, later = {t: [] for t in TOWNS}, {t: [] for t in TOWNS}
    for town_index, town in enumerate(TOWNS):
        for i in range(20):
            person = dict(person=f"person-{town_index}-{i}", given=rng.choice(GIVEN),
                          surname=rng.choice(SURNAMES), birth=str(rng.randint(1865, 1895)),
                          role=rng.choice(ROLES), address=f"Marktstrasse {rng.randint(1, 40)}")
            if i < 2:
                person.update(given="Emil", surname="Meyer", birth="", role="clerk", address="")
            early[town].append(person)
            if i < 16:
                other = dict(person)
                if i >= 2:
                    if rng.random() < .28:
                        other["given"] = other["given"][0] + "."
                    other["surname"] = other["surname"].replace("ü", "ue").replace("ä", "ae")
                    if rng.random() < .18:
                        # One simulated recognition error; the original value is not in the page.
                        other["surname"] = other["surname"][:-1] + "n"
                    if rng.random() < .2:
                        other["birth"] = ""
                    if rng.random() < .12:
                        other["role"] = rng.choice(ROLES)
                    if rng.random() < .25:
                        other["address"] = ""
                target = town
                if i in (14, 15):
                    group_start = (town_index // 4) * 4
                    target = TOWNS[group_start + (town_index + 1) % 4]
                later[target].append(other)
        for i in range(4):
            later[town].append(dict(person=f"entrant-{town_index}-{i}", given=rng.choice(GIVEN),
                                    surname=rng.choice(SURNAMES), birth=str(rng.randint(1865, 1895)),
                                    role=rng.choice(ROLES), address=f"Gartenweg {rng.randint(1, 40)}"))
    identities = {1920: {}, 1930: {}}
    for year, register in ((1920, early), (1930, later)):
        for index, town in enumerate(TOWNS):
            people = list(register[town])
            rng.shuffle(people)
            page = f"register_{year}_{index + 1:02d}.txt"
            lines = ["SYNTHETIC MUNICIPAL REGISTER — fictional people and places",
                     f"Municipality: {town}", f"Year: {year}", ""]
            for number, p in enumerate(people, 1):
                if year == 1920:
                    row = f"{number:02d} | {p['surname']}, {p['given']} | b. {p['birth'] or '?'} | {p['role']} | {p['address'] or '?'}"
                else:
                    row = f"{number:02d}. {p['given']} {p['surname']} ; born {p['birth'] or '?'} ; role={p['role']} ; addr={p['address'] or '?'}"
                lines.append(row)
                identities[year][p["person"]] = f"{Path(page).stem}:L{len(lines):03d}"
            lines.append("[illegible fragment: row structure could not be recovered]")
            (pages / page).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    with (destination / "truth.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["left_id", "right_id", "town", "split"], lineterminator="\n")
        writer.writeheader()
        for index, town in enumerate(TOWNS):
            for p in early[town]:
                writer.writerow(dict(left_id=identities[1920][p["person"]],
                                     right_id=identities[1930].get(p["person"], ""), town=town,
                                     split="development" if index < 4 else "heldout"))
    return destination


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "data")
    parser.add_argument("--seed", type=int, default=20260916)
    args = parser.parse_args()
    make_dataset(args.output, args.seed)
