import argparse
import difflib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
JOURNAL_FILE = ROOT / "builtin_journals.json"
REQUIRED_FIELDS = [
    "name",
    "full_name",
    "openalex_query",
    "openalex_source_id",
    "url",
    "publisher",
    "sub",
    "issn",
    "code",
    "doi_prefix",
    "source_type",
]


def normalize_text(value):
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def normalize_issn(value):
    return (value or "").replace("-", "").lower()


def source_id(source):
    return (source.get("id") or "").split("/")[-1]


def source_issns(source):
    values = []
    for key in ("issn", "issn_l"):
        value = source.get(key)
        if isinstance(value, list):
            values.extend(value)
        elif value:
            values.append(value)
    return {str(value).lower() for value in values if value}


def add_issue(issues, issue_type, journal, **details):
    issue = {
        "type": issue_type,
        "name": journal.get("name", ""),
    }
    issue.update(details)
    issues.append(issue)


def expected_doi_prefix(journal):
    url = journal.get("url", "")
    host = urllib.parse.urlparse(url).netloc.lower()
    if "rss.sciencedirect.com" in host or "cell.com" in host:
        return "10.1016"
    if "pnas.org" in host:
        return "10.1073"
    if "plos.org" in host:
        return "10.1371"
    if "elifesciences.org" in host:
        return "10.7554"
    if "mdpi.com" in host:
        return "10.3390"
    if "feeds.aps.org" in host:
        return "10.1103"
    if "acs.org" in host or "pubs.acs.org" in host:
        return "10.1021"
    if "rsc.org" in host:
        return "10.1039"
    if "tandfonline.com" in host:
        return "10.1080"
    if "thieme-connect.de" in host:
        return "10.1055"
    return ""


def validate_local(journals):
    issues = []
    for journal in journals:
        missing = [field for field in REQUIRED_FIELDS if field not in journal]
        if missing:
            add_issue(issues, "missing_fields", journal, fields=missing)

        url = journal.get("url", "")
        if not re.match(r"^https?://", url):
            add_issue(issues, "bad_url", journal, url=url)

        issn = journal.get("issn", "")
        if issn and not re.match(r"^\d{4}-\d{3}[\dXx]$", issn):
            add_issue(issues, "bad_issn", journal, issn=issn)

        doi_prefix = journal.get("doi_prefix", "")
        if doi_prefix and not re.match(r"^10\.\d{4,9}$", doi_prefix):
            add_issue(issues, "bad_doi_prefix", journal, doi_prefix=doi_prefix)

        expected_prefix = expected_doi_prefix(journal)
        if expected_prefix and doi_prefix != expected_prefix:
            add_issue(
                issues,
                "doi_prefix_mismatch",
                journal,
                current=doi_prefix,
                expected=expected_prefix,
                url=url,
            )

        match = re.search(r"/publication/science/(\d{8})", url)
        if match and issn and normalize_issn(issn) != match.group(1):
            add_issue(
                issues,
                "sciencedirect_issn_mismatch",
                journal,
                current=issn,
                expected_digits=match.group(1),
                url=url,
            )

    url_counts = Counter(journal.get("url", "").lower() for journal in journals)
    for url, count in url_counts.items():
        if url and count > 1:
            issues.append({"type": "duplicate_url", "url": url, "count": count})

    name_counts = Counter(
        (journal.get("name", "").lower(), journal.get("source_type", ""))
        for journal in journals
    )
    for (name, source_type), count in name_counts.items():
        if name and count > 1:
            issues.append({
                "type": "duplicate_name_source_type",
                "name": name,
                "source_type": source_type,
                "count": count,
            })
    return issues


def request_json(url, timeout, retries, delay):
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "FolPaper-journal-audit/1.0"},
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == retries:
                raise
            time.sleep(delay * (attempt + 2))
    return None


def choose_source(results, query):
    normalized_query = normalize_text(query)
    journal_results = [
        source for source in results
        if (source.get("type") or "").lower() == "journal"
    ] or results
    for source in journal_results:
        names = [source.get("display_name", "")] + (source.get("alternate_titles") or [])
        if any(normalize_text(name) == normalized_query for name in names):
            return source
    return journal_results[0] if journal_results else None


def lookup_openalex_source(journal, args):
    query = journal.get("openalex_query") or journal.get("full_name") or journal.get("name")
    if journal.get("openalex_source_id"):
        clean_id = journal["openalex_source_id"].split("/")[-1]
        url = f"https://api.openalex.org/sources/{urllib.parse.quote(clean_id)}"
        return request_json(url, args.timeout, args.retries, args.delay), "source_id"

    if journal.get("issn"):
        url = "https://api.openalex.org/sources?filter=issn:" + urllib.parse.quote(journal["issn"]) + "&per-page=5"
        source = choose_source(request_json(url, args.timeout, args.retries, args.delay).get("results", []), query)
        if source:
            return source, "issn"

    url = "https://api.openalex.org/sources?search=" + urllib.parse.quote(query) + "&per-page=5"
    return choose_source(request_json(url, args.timeout, args.retries, args.delay).get("results", []), query), "search"


def validate_openalex(journals, args):
    issues = []
    checked = 0
    matched = 0
    for journal in journals:
        if journal.get("source_type") != "journal":
            continue
        if args.limit and checked >= args.limit:
            break
        checked += 1

        try:
            source, method = lookup_openalex_source(journal, args)
        except Exception as error:
            add_issue(issues, "openalex_request_error", journal, detail=str(error)[:160])
            time.sleep(args.delay)
            continue

        if not source:
            add_issue(issues, "openalex_no_match", journal)
            time.sleep(args.delay)
            continue

        matched += 1
        display_name = source.get("display_name", "")
        candidate_names = [display_name] + (source.get("alternate_titles") or [])
        local_names = [
            normalize_text(journal.get("openalex_query")),
            normalize_text(journal.get("full_name")),
            normalize_text(journal.get("name")),
        ]
        exact_match = any(normalize_text(name) in local_names for name in candidate_names)
        ratio = max(
            [difflib.SequenceMatcher(None, name, normalize_text(display_name)).ratio() for name in local_names if name]
            or [0]
        )

        if (source.get("type") or "").lower() != "journal":
            add_issue(issues, "openalex_not_journal", journal, matched=display_name, method=method)
        if journal.get("issn") and journal["issn"].lower() not in source_issns(source):
            add_issue(
                issues,
                "openalex_issn_mismatch",
                journal,
                current=journal["issn"],
                matched=display_name,
                openalex_issn=sorted(source_issns(source)),
                method=method,
            )
        if journal.get("openalex_source_id") and journal["openalex_source_id"].split("/")[-1] != source_id(source):
            add_issue(
                issues,
                "openalex_source_id_mismatch",
                journal,
                current=journal["openalex_source_id"],
                matched_id=source_id(source),
                matched=display_name,
            )
        if not exact_match and ratio < args.name_ratio:
            add_issue(
                issues,
                "openalex_weak_name_match",
                journal,
                query=journal.get("openalex_query"),
                matched=display_name,
                ratio=round(ratio, 2),
                method=method,
            )
        time.sleep(args.delay)

    return issues, checked, matched


def print_summary(journals, local_issues, openalex_issues=None, checked=0, matched=0):
    print(f"records={len(journals)}")
    print("source_types=" + json.dumps(dict(Counter(j.get("source_type") for j in journals)), sort_keys=True))
    print(f"empty_issn={sum(1 for journal in journals if not journal.get('issn'))}")
    print(f"empty_openalex_source_id={sum(1 for journal in journals if not journal.get('openalex_source_id'))}")
    print(f"empty_doi_prefix={sum(1 for journal in journals if not journal.get('doi_prefix'))}")
    print(f"local_issues={len(local_issues)}")
    print("local_issue_counts=" + json.dumps(dict(Counter(issue["type"] for issue in local_issues)), sort_keys=True))
    if openalex_issues is not None:
        print(f"openalex_checked={checked}")
        print(f"openalex_matched={matched}")
        print(f"openalex_issues={len(openalex_issues)}")
        print("openalex_issue_counts=" + json.dumps(dict(Counter(issue["type"] for issue in openalex_issues)), sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description="Validate builtin_journals.json.")
    parser.add_argument("--openalex", action="store_true", help="Validate journal metadata against OpenAlex with throttling.")
    parser.add_argument("--delay", type=float, default=3.0, help="Delay between OpenAlex requests in seconds. Keep this high without an API key.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum journal records to validate against OpenAlex. 0 means all.")
    parser.add_argument("--timeout", type=float, default=20.0, help="OpenAlex request timeout in seconds.")
    parser.add_argument("--retries", type=int, default=2, help="Retries for OpenAlex 429 responses.")
    parser.add_argument("--name-ratio", type=float, default=0.72, help="Minimum fuzzy ratio before reporting weak name matches.")
    parser.add_argument("--json", action="store_true", help="Print issue details as JSON lines.")
    args = parser.parse_args()

    journals = json.loads(JOURNAL_FILE.read_text(encoding="utf-8"))
    local_issues = validate_local(journals)
    openalex_issues = None
    checked = matched = 0
    if args.openalex:
        openalex_issues, checked, matched = validate_openalex(journals, args)

    print_summary(journals, local_issues, openalex_issues, checked, matched)
    if args.json:
        for issue in local_issues + (openalex_issues or []):
            print(json.dumps(issue, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
