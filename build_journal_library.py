import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE_FILE = ROOT / "学术期刊预印本RSS链接汇总.md"
OUTPUT_FILE = ROOT / "builtin_journals.json"


PUBLISHER_DOI_PREFIXES = (
    ("ScienceDirect", "10.1016"),
    ("Elsevier", "10.1016"),
    ("Cell Press", "10.1016"),
    ("Nature", "10.1038"),
    ("Science", "10.1126"),
    ("ACS", "10.1021"),
    ("RSC", "10.1039"),
    ("Wiley", "10.1002"),
    ("APS", "10.1103"),
    ("PNAS", "10.1073"),
    ("Thieme", "10.1055"),
    ("PLOS", "10.1371"),
    ("Springer", "10.1007"),
    ("Oxford", "10.1093"),
    ("OUP", "10.1093"),
    ("MDPI", "10.3390"),
    ("Taylor", "10.1080"),
)


OPENALEX_NAME_ALIASES = {
    "J. Am. Chem. Soc.": "Journal of the American Chemical Society",
    "J. Agricultural and Food Chemistry": "Journal of Agricultural and Food Chemistry",
    "J. Medicinal Chemistry": "Journal of Medicinal Chemistry",
    "J. Natural Products": "Journal of Natural Products",
    "J. Proteome Research": "Journal of Proteome Research",
    "J. Chemical & Engineering Data": "Journal of Chemical & Engineering Data",
    "J. Chemical Education": "Journal of Chemical Education",
    "J. Chemical Information and Modeling": "Journal of Chemical Information and Modeling",
    "J. Chemical Theory and Computation": "Journal of Chemical Theory and Computation",
    "J. Physical Chemistry A": "Journal of Physical Chemistry A",
    "J. Physical Chemistry B": "Journal of Physical Chemistry B",
    "J. Physical Chemistry C": "Journal of Physical Chemistry C",
    "J. Physical Chemistry Letters": "Journal of Physical Chemistry Letters",
    "J. Analytical Atomic Spectrometry": "Journal of Analytical Atomic Spectrometry",
    "J. Organometallic Chemistry": "Journal of Organometallic Chemistry",
    "J. Pharmaceutical Sciences": "Journal of Pharmaceutical Sciences",
    "Int. J. Pharmaceutics": "International Journal of Pharmaceutics",
    "J. Controlled Release": "Journal of Controlled Release",
    "J. Ethnopharmacology": "Journal of Ethnopharmacology",
    "J. Food Composition and Analysis": "Journal of Food Composition and Analysis",
    "J. Chromatography A": "Journal of Chromatography A",
    "J. Chromatography B": "Journal of Chromatography B",
    "J. Pharmaceutical and Biomedical Analysis": "Journal of Pharmaceutical and Biomedical Analysis",
    "J. Biomedical Informatics": "Journal of Biomedical Informatics",
    "Angewandte Chemie Int. Ed.": "Angewandte Chemie International Edition",
    "European J. Medicinal Chemistry": "European Journal of Medicinal Chemistry",
    "European J. Organic Chemistry": "European Journal of Organic Chemistry",
    "European J. Pharmaceutics and Biopharmaceutics": "European Journal of Pharmaceutics and Biopharmaceutics",
    "European J. Pharmaceutical Sciences": "European Journal of Pharmaceutical Sciences",
    "Asian J. Organic Chemistry": "Asian Journal of Organic Chemistry",
    "Chinese J. Chemistry": "Chinese Journal of Chemistry",
    "J. Heterocyclic Chemistry": "Journal of Heterocyclic Chemistry",
    "British J. Clinical Pharmacology": "British Journal of Clinical Pharmacology",
    "J. Food Science": "Journal of Food Science",
    "J. Science of Food and Agriculture": "Journal of the Science of Food and Agriculture",
    "J. Mass Spectrometry": "Journal of Mass Spectrometry",
    "Rapid Comm. Mass Spectrometry": "Rapid Communications in Mass Spectrometry",
    "J. Computational Chemistry": "Journal of Computational Chemistry",
    "J. Computer-Aided Molecular Design": "Journal of Computer-Aided Molecular Design",
    "J. Electroanalytical Chemistry": "Journal of Electroanalytical Chemistry",
    "J. Cheminformatics": "Journal of Cheminformatics",
    "J. Asian Natural Products Research": "Journal of Asian Natural Products Research",
    "J. Pharmaceutical & Biomedical Analysis": "Journal of Pharmaceutical and Biomedical Analysis",
    "J. Pharmacology & Experimental Therapeutics": "Journal of Pharmacology and Experimental Therapeutics",
    "J. Natural Medicines": "Journal of Natural Medicines",
    "C&EN Latest News": "Chemical & Engineering News",
}


JOURNAL_METADATA_OVERRIDES = {
    "PNAS": {"doi_prefix": "10.1073"},
    "eLife": {"doi_prefix": "10.7554"},
    "PLOS Biology": {"doi_prefix": "10.1371"},
    "PLOS ONE": {"doi_prefix": "10.1371"},
    "PLOS Genetics": {"doi_prefix": "10.1371"},
    "PLOS Pathogens": {"doi_prefix": "10.1371"},
    "PLOS Computational Biology": {"doi_prefix": "10.1371"},
    "J. Am. Chem. Soc.": {"issn": "0002-7863", "openalex_source_id": "S111155417"},
    "J. Agricultural and Food Chemistry": {"issn": "0021-8561", "openalex_source_id": "S134644764"},
    "J. Medicinal Chemistry": {"issn": "0022-2623", "openalex_source_id": "S162030435"},
    "J. Natural Products": {"issn": "0163-3864"},
    "J. Proteome Research": {"issn": "1535-3893"},
    "J. Chemical & Engineering Data": {"issn": "0021-9568"},
    "J. Chemical Education": {"issn": "0021-9584"},
    "J. Chemical Information and Modeling": {"issn": "1549-9596", "openalex_source_id": "S167262187"},
    "J. Chemical Theory and Computation": {"issn": "1549-9618", "openalex_source_id": "S189701308"},
    "J. Physical Chemistry A": {"issn": "1089-5639"},
    "J. Physical Chemistry B": {"issn": "1520-6106"},
    "J. Physical Chemistry C": {"issn": "1932-7447"},
    "J. Physical Chemistry Letters": {"issn": "1948-7185"},
}


def strip_markup(value):
    value = value.strip()
    value = re.sub(r"`([^`]*)`", r"\1", value)
    value = re.sub(r"\*\*([^*]*)\*\*", r"\1", value)
    value = re.sub(r"\[(.*?)\]\([^)]*\)", r"\1", value)
    value = value.replace("—", "").strip()
    return value


def clean_heading(value):
    value = strip_markup(value)
    value = re.sub(r"^[一二三四五六七八九十]+、", "", value)
    value = re.sub(r"^[\d.]+\s*", "", value)
    value = re.sub(r"^[^\w\u4e00-\u9fff]+", "", value).strip()
    return value


def split_row(line):
    cells = [strip_markup(cell) for cell in line.strip().strip("|").split("|")]
    return cells


def extract_url(value):
    match = re.search(r"https?://[^\s`|]+", value)
    return match.group(0) if match else ""


def publisher_doi_prefix(publisher):
    normalized = publisher.lower()
    for key, prefix in PUBLISHER_DOI_PREFIXES:
        pattern = r"(?<![a-z])" + re.escape(key.lower()) + r"(?![a-z])"
        if re.search(pattern, normalized):
            return prefix
    return ""


def source_type(publisher, name):
    if "预印本" in publisher:
        return "preprint"
    if name.startswith("cs.") or name.startswith("stat.") or name.startswith("q-bio.") or name.startswith("physics.") or name.startswith("cond-mat."):
        return "preprint"
    return "journal"


def parse_markdown():
    journals = []
    seen = set()
    publisher = "其他"
    subsection = "其他"
    lines = SOURCE_FILE.read_text(encoding="utf-8").splitlines()
    index = 0

    while index < len(lines):
        line = lines[index]
        if line.startswith("## "):
            publisher = clean_heading(line[3:])
            subsection = "其他"
            index += 1
            continue
        if line.startswith("### "):
            subsection = clean_heading(line[4:])
            index += 1
            continue

        if line.startswith("|") and index + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[index + 1].strip()):
            headers = split_row(line)
            lowered_headers = [header.lower() for header in headers]
            if "rss url" not in lowered_headers:
                index += 1
                continue
            if not any(header in headers for header in ["期刊", "分类", "学科", "类型", "来源"]):
                index += 1
                continue

            url_index = lowered_headers.index("rss url")
            name_index = next((headers.index(header) for header in ["期刊", "分类", "学科", "类型", "来源"] if header in headers), 0)
            issn_index = headers.index("ISSN") if "ISSN" in headers else None
            code_index = next((headers.index(header) for header in ["简写", "Code"] if header in headers), None)

            index += 2
            while index < len(lines) and lines[index].startswith("|"):
                cells = split_row(lines[index])
                if len(cells) <= max(name_index, url_index):
                    index += 1
                    continue

                name = cells[name_index]
                url = extract_url(cells[url_index])
                if not name or not url or name in ["期刊", "分类", "学科", "类型", "来源"]:
                    index += 1
                    continue

                key = (name.lower(), url.lower())
                if key in seen:
                    index += 1
                    continue
                seen.add(key)

                issn = cells[issn_index] if issn_index is not None and issn_index < len(cells) else ""
                code = cells[code_index] if code_index is not None and code_index < len(cells) else ""
                openalex_query = OPENALEX_NAME_ALIASES.get(name, name)
                metadata = JOURNAL_METADATA_OVERRIDES.get(name, {})

                journals.append({
                    "name": name,
                    "full_name": openalex_query,
                    "openalex_query": openalex_query,
                    "openalex_source_id": metadata.get("openalex_source_id", ""),
                    "url": url,
                    "publisher": publisher,
                    "sub": subsection,
                    "issn": metadata.get("issn") or issn,
                    "code": code,
                    "doi_prefix": metadata.get("doi_prefix") or publisher_doi_prefix(publisher),
                    "source_type": source_type(publisher, name),
                })
                index += 1
            continue
        index += 1
    return journals


def main():
    journals = parse_markdown()
    OUTPUT_FILE.write_text(json.dumps(journals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(journals)} journal records -> {OUTPUT_FILE.name}")


if __name__ == "__main__":
    main()
