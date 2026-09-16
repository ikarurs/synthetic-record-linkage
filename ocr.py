"""Read page pixels with Gemini, or verify and replay the saved real responses."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
PROMPT = '''Read this redacted historical German address-book excerpt visually. Return a full plain-text
transcription in reading order, and extract every explicitly named person in an
institutional section. Preserve the printed name, role (function), title (rank or
honorific), address and heading hierarchy separately. Do not expand initials, fix
names, infer identity, or invent missing text. Names after a comma remain as printed.
Addresses, office hours, telephone numbers and unnamed positions are not people.
institution_path lists visible headings from broadest to most specific. Do not add
the page banner to the hierarchy. For entries continuing from the previous page
without a visible institution, set continued=true and institution_path=[]. Do not
invent the previous heading. Record active_hierarchy_at_end for the last section.
Black rectangles conceal identifying source details. Transcribe them as [redacted]
and never infer the city, year, source, or hidden words. A crop may begin mid-section;
leave the hierarchy empty for those entries rather than inventing a heading.
raw_entry is the printed entry, joining line wraps. Empty role/title/address values are strings.
If no named people qualify, return entries=[] and explain the visible evidence in
empty_result_reason; otherwise that reason is empty. confidence is your self-rated
confidence in reading the page completely and correctly, not an accuracy estimate.'''


def object_schema(properties):
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)


TEXT = {'type': 'string'}
TEXTS = {'type': 'array', 'items': TEXT}
SCHEMA = object_schema(dict(
    transcription=TEXT, confidence={'type': 'number', 'minimum': 0, 'maximum': 1},
    empty_result_reason=TEXT, active_hierarchy_at_end=TEXTS,
    entries={'type': 'array', 'items': object_schema(dict(
        name=TEXT, role=TEXT, title=TEXT, address=TEXT, institution_path=TEXTS,
        continued={'type': 'boolean'}, raw_entry=TEXT))}))
CONFIG = dict(maxOutputTokens=32768, thinkingConfig={'thinkingLevel':'low'},
              responseMimeType='application/json', responseJsonSchema=SCHEMA)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def validate(page):
    if not isinstance(page, dict) or set(page) != set(SCHEMA['properties']):
        raise ValueError('Invalid page fields')
    if not isinstance(page['transcription'], str) or not page['transcription'].strip():
        raise ValueError('Missing transcription')
    if not isinstance(page['confidence'], (int, float)) or not 0 <= page['confidence'] <= 1:
        raise ValueError('Invalid page confidence')
    if not isinstance(page['entries'], list):
        raise ValueError('Entries must be a list')
    if not isinstance(page['empty_result_reason'], str) or (not page['entries'] and not page['empty_result_reason'].strip()):
        raise ValueError('An empty page needs an evidence-based reason')
    for entry in page['entries']:
        if not isinstance(entry, dict) or set(entry) != set(SCHEMA['properties']['entries']['items']['properties']):
            raise ValueError('Invalid entry fields')
        if not all(isinstance(entry[k], str) for k in ('name', 'role', 'title', 'address', 'raw_entry')):
            raise ValueError('Invalid entry text')
        if not entry['name'].strip() or not isinstance(entry['continued'], bool):
            raise ValueError('Invalid named entry')
    for path in [page['active_hierarchy_at_end'], *[e['institution_path'] for e in page['entries']]]:
        if not isinstance(path, list) or not all(isinstance(p, str) for p in path):
            raise ValueError('Invalid hierarchy')
    return page


def read_page(meta, live=False, model='gemini-3.5-flash'):
    image = (ROOT / 'data' / meta['image']).read_bytes()
    signature = dict(image_sha256=digest(image), prompt_sha256=digest(PROMPT.encode()),
                     schema_sha256=digest(json.dumps(SCHEMA, sort_keys=True).encode()),
                     config_sha256=digest(json.dumps(CONFIG, sort_keys=True).encode()))
    target = ROOT / 'data' / 'ocr' / f"{meta['page_id']}.json"
    if not live:
        saved = json.loads(target.read_text(encoding='utf-8'))
        if any(saved.get(k) != v for k, v in signature.items()):
            raise ValueError(f"Stale OCR cache: {meta['page_id']}; rerun live OCR explicitly")
        validate(saved['page'])
        return saved
    key = os.environ.get('GOOGLE_API_KEY')
    if not key:
        raise ValueError('Set GOOGLE_API_KEY in the environment for live OCR')
    body = dict(contents=[dict(role='user', parts=[{'text': PROMPT},
        {'inlineData': {'mimeType': 'image/png', 'data': base64.b64encode(image).decode()}}])],
        generationConfig=CONFIG)
    request = urllib.request.Request(
        f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
        data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'x-goog-api-key': key})
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'OCR HTTP {exc.code} for {meta["page_id"]}') from None
    candidate = payload.get('candidates', [{}])[0]
    if candidate.get('finishReason') != 'STOP':
        raise ValueError(f'Incomplete OCR response: {candidate.get("finishReason")}')
    raw = ''.join(p.get('text', '') for p in candidate['content']['parts'] if not p.get('thought'))
    saved = dict(**signature, model=payload.get('modelVersion', model),
                 captured_utc=datetime.now(timezone.utc).isoformat(),
                 usage=payload.get('usageMetadata', {}), generation_config=CONFIG, raw_response_text=raw,
                 page=validate(json.loads(raw)))
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(saved, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    temporary.replace(target)
    return saved


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Send only included redacted images to Google; API charges apply')
    parser.add_argument('--model', default='gemini-3.5-flash')
    parser.add_argument('--page', help='Optional single page_id')
    args = parser.parse_args()
    for meta in json.loads((ROOT / 'data' / 'manifest.json').read_text(encoding='utf-8')):
        if not args.page or args.page == meta['page_id']:
            result = read_page(meta, args.live, args.model)
            print(meta['page_id'], len(result['page']['entries']), 'people', flush=True)
