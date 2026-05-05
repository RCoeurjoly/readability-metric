# -*- coding: utf-8 -*-
"""Readability metrics for EPUB books."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import re
import subprocess
import sys
import unicodedata
import warnings
import zipfile
from collections import Counter
from pathlib import Path
from posixpath import dirname, join, normpath

import ebooklib
import numpy as np
import pymongo
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from ebooklib import epub
from langdetect import DetectorFactory, LangDetectException, detect
from lxml import etree
from scipy.optimize import OptimizeWarning, curve_fit


ANALYSIS_VERSION = "2.0"
DEFAULT_SAMPLES = 10
DEFAULT_MAX_SIZE_MB = 10.0
LANGUAGE_DETECTION_LIMIT = 50000

DetectorFactory.seed = 0

PRINTABLE = {
    "Cf",
    "Cn",
    "Co",
    "Cs",
    "LC",
    "Ll",
    "Lm",
    "Lo",
    "Lt",
    "Lu",
    "Mc",
    "Me",
    "Mn",
    "Nd",
    "Nl",
    "No",
    "Pc",
    "Pd",
    "Pe",
    "Pf",
    "Pi",
    "Po",
    "Ps",
    "Sc",
    "Sk",
    "Sm",
    "So",
    "Zl",
    "Zp",
    "Zs",
}

WORD_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.UNICODE)
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def lexical_sweep_map(start, stop, step, text):
    return list(map(lambda x: [x, len(set(text[0:x]))], range(int(start), int(stop), int(step))))


def lexical_sweep_list_comprehension(start, stop, step, text):
    return [[x, len(set(text[0:x]))] for x in range(int(start), int(stop), int(step))]


def lexical_sweep_for_loop(start, stop, step, text):
    sweep_values = []
    for x_value in range(int(start), int(stop), int(step)):
        sweep_values.append([x_value, len(set(text[0:x_value]))])
    return sweep_values


def lexical_sweep(text, slicing_function=lexical_sweep_map, samples=DEFAULT_SAMPLES):
    """Calculate vocabulary growth samples across a token sequence."""
    try:
        log_behaviour_start = 5000
        log_behaviour_range = len(text) - log_behaviour_start
        if len(text) > 10000 and samples >= 2:
            log_step = log_behaviour_range / (samples - 1)
            if slicing_function in (
                lexical_sweep_map,
                lexical_sweep_list_comprehension,
                lexical_sweep_for_loop,
            ):
                sample_points = list(range(log_behaviour_start, len(text) + 1, int(log_step)))
                return lexical_sweep_one_pass(text, sample_points)
            return slicing_function(log_behaviour_start, len(text) + 1, log_step, text)
        return False
    except (AttributeError, TypeError, ValueError) as ex:
        print(ex)
        return False


def lexical_sweep_one_pass(text, sample_points):
    sweep_values = []
    seen = set()
    next_sample = 0
    for position, token in enumerate(text, start=1):
        seen.add(token)
        while next_sample < len(sample_points) and position >= sample_points[next_sample]:
            sweep_values.append([sample_points[next_sample], len(seen)])
            next_sample += 1
    return sweep_values


def linear_func(variable, slope, y_intercept):
    """Linear model."""
    return slope * variable + y_intercept


def log_func(variable, coefficient, x_intercept):
    """Logarithmic model."""
    return coefficient * np.log(variable) + x_intercept


def log_log_func(variable, coefficient, intercept):
    """Log-log model."""
    return math.e ** (coefficient * np.log(variable) + intercept)


def clean_non_printable(text):
    """Remove non-printable Unicode categories from a string."""
    return "".join(character for character in text if unicodedata.category(character) in PRINTABLE)


def clean_dots(dictionary):
    """Remove dot from a dictionary when present."""
    dictionary.pop(".", None)


def is_chinese_language(language_code):
    return bool(language_code) and language_code.lower().replace("_", "-").startswith("zh")


def detect_language_code(text):
    sample = " ".join(text.split())[:LANGUAGE_DETECTION_LIMIT]
    if not sample:
        return "unknown"
    try:
        return detect(sample)
    except LangDetectException:
        return "unknown"


def tokenize_words(text, language_code=None):
    if is_chinese_language(language_code):
        return CJK_RE.findall(text)
    return WORD_RE.findall(text.casefold())


def json_ready(value):
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def read_epub_opf(epub_path):
    with zipfile.ZipFile(epub_path) as archive:
        try:
            container = etree.fromstring(archive.read("META-INF/container.xml"))
            rootfile = container.find(
                ".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile"
            )
            opf_path = rootfile.get("full-path") if rootfile is not None else None
        except (KeyError, etree.XMLSyntaxError, AttributeError):
            opf_path = None
        if not opf_path:
            opf_candidates = [name for name in archive.namelist() if name.lower().endswith(".opf")]
            if not opf_candidates:
                raise ebooklib.epub.EpubException("EPUB has no OPF package document")
            opf_path = opf_candidates[0]
        parser = etree.XMLParser(recover=True)
        return opf_path, etree.fromstring(archive.read(opf_path), parser=parser)


def first_text(root, expression, namespaces):
    values = root.xpath(expression, namespaces=namespaces)
    for value in values:
        if isinstance(value, str):
            text = value.strip()
        else:
            text = (value.text or "").strip()
        if text:
            return text
    return None


def fallback_epub_metadata(epub_path):
    _, root = read_epub_opf(epub_path)
    namespaces = {"dc": "http://purl.org/dc/elements/1.1/"}
    metadata_fields = [
        "creator",
        "title",
        "subject",
        "source",
        "rights",
        "relation",
        "publisher",
        "identifier",
        "description",
        "coverage",
        "contributor",
        "date",
    ]
    metadata = {}
    for field in metadata_fields:
        value = first_text(root, f".//dc:{field}", namespaces)
        if value:
            metadata[field] = value
    for attribute, field in (
        ("original_language", "language"),
        ("epub_type", "type"),
        ("epub_format", "format"),
    ):
        value = first_text(root, f".//dc:{field}", namespaces)
        if value:
            metadata[attribute] = value
    return metadata


def fallback_epub_text(epub_path):
    opf_path, root = read_epub_opf(epub_path)
    opf_dir = dirname(opf_path)
    manifest_items = root.xpath(
        './/*[local-name()="manifest"]/*[local-name()="item"]'
    )
    item_by_id = {item.get("id"): item for item in manifest_items}
    spine_ids = [
        item.get("idref")
        for item in root.xpath('.//*[local-name()="spine"]/*[local-name()="itemref"]')
        if item.get("idref")
    ]
    ordered_items = [item_by_id[item_id] for item_id in spine_ids if item_id in item_by_id]
    if not ordered_items:
        ordered_items = manifest_items

    text_parts = []
    with zipfile.ZipFile(epub_path) as archive:
        for item in ordered_items:
            href = item.get("href")
            media_type = item.get("media-type", "")
            if not href:
                continue
            if media_type not in ("application/xhtml+xml", "text/html") and not href.lower().endswith(
                (".xhtml", ".html", ".htm")
            ):
                continue
            item_path = normpath(join(opf_dir, href))
            try:
                raw_html = archive.read(item_path)
            except KeyError:
                continue
            if not raw_html:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
                text_parts.append(BeautifulSoup(raw_html, "lxml").get_text(" "))
    return clean_non_printable(" ".join(text_parts))


class Book(object):
    """EPUB book metadata and readability metrics."""

    def __init__(self, epub_filename, slicing_function=lexical_sweep_map, samples=0, verbose=False):
        self.verbose = verbose
        self._log("Extracting metadata")
        self.extract_metadata(epub_filename)
        if samples:
            self._log("Extracting text")
            self.extract_text()
            self._log("Detecting language")
            self.detect_language()
            self._log("Tokenization")
            self.tokenize()
            self._log("Calculating word sweep values")
            sweep_values = lexical_sweep(self.tokens, slicing_function, samples)
            self._log("Word fit")
            self.extract_fit_parameters("words", sweep_values)
            if is_chinese_language(self.language):
                self._log("Calculating character sweep values")
                sweep_values = lexical_sweep(self.zh_characters, slicing_function, samples)
                self._log("Character fit")
                self.extract_fit_parameters("characters", sweep_values)
            self.delete_heavy_attributes()

    def _log(self, message):
        if self.verbose:
            print(message)

    def extract_metadata(self, epub_filename):
        """Extract Dublin Core metadata from an EPUB."""
        self.filepath = str(epub_filename)
        metadata_fields = [
            "creator",
            "title",
            "subject",
            "source",
            "rights",
            "relation",
            "publisher",
            "identifier",
            "description",
            "coverage",
            "contributor",
            "date",
        ]
        try:
            epub_file = epub.read_epub(self.filepath)
        except (TypeError, KeyError, AttributeError, etree.XMLSyntaxError, ebooklib.epub.EpubException):
            for attribute, value in fallback_epub_metadata(self.filepath).items():
                setattr(self, attribute, value)
            return
        for metadata_field in metadata_fields:
            try:
                setattr(self, metadata_field, epub_file.get_metadata("DC", metadata_field)[0][0])
            except (IndexError, AttributeError):
                pass
        metadata_to_attribute = [
            ["original_language", "language"],
            ["epub_type", "type"],
            ["epub_format", "format"],
        ]
        for attribute, metadata_field in metadata_to_attribute:
            try:
                setattr(self, attribute, epub_file.get_metadata("DC", metadata_field)[0][0])
            except (IndexError, AttributeError):
                pass

    def extract_text(self):
        """Extract text content from document items in the EPUB."""
        try:
            book = epub.read_epub(self.filepath)
        except (TypeError, KeyError, AttributeError, etree.XMLSyntaxError, ebooklib.epub.EpubException):
            self.text = fallback_epub_text(self.filepath)
            return
        html_filtered = ""
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                raw_html = item.get_content()
                if not raw_html:
                    continue
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
                    html_filtered += BeautifulSoup(raw_html, "lxml").get_text(" ")
                html_filtered += " "
        self.text = clean_non_printable(html_filtered)

    def detect_language(self):
        """Detect language from extracted text rather than trusting EPUB metadata."""
        if not hasattr(self, "text"):
            self.extract_text()
        self.language = detect_language_code(self.text)

    def tokenize(self):
        """Tokenize the extracted text."""
        try:
            if is_chinese_language(getattr(self, "language", None)):
                self.zh_characters = "".join(CJK_RE.findall(self.text))
                self.character_count = len(self.zh_characters)
                self.unique_characters = len(set(self.zh_characters))
            self.tokens = tokenize_words(self.text, getattr(self, "language", None))
            self.word_count = len(self.tokens)
            self.unique_words = len(set(self.tokens))
        except ValueError as ex:
            print(ex)
            self.tokens = []

    def get_freq_dist(self):
        """Frequency distribution for tokens and Chinese characters."""
        if not getattr(self, "tokens", None):
            self.tokenize()
        if is_chinese_language(getattr(self, "language", None)):
            self.zh_char_freq_dist = dict(Counter(self.zh_characters))
            clean_dots(self.zh_char_freq_dist)
        self.freq_dist = dict(Counter(self.tokens))
        clean_dots(self.freq_dist)

    def extract_fit_parameters(self, analysis_type, sweep_values):
        """Fit vocabulary growth samples to a linear model in log space."""
        log_x = True
        log_y = analysis_type == "words"
        if not sweep_values:
            return
        values = np.asarray(sweep_values, dtype=float)
        xarr = np.log(values[:, 0]) if log_x else values[:, 0]
        yarr = np.log(values[:, 1]) if log_y else values[:, 1]
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", OptimizeWarning)
                popt, pcov = curve_fit(linear_func, xarr, yarr, (0, 0))
        except (OptimizeWarning, RuntimeError, ValueError, FloatingPointError) as ex:
            print(ex)
            return
        perr = np.sqrt(np.diag(pcov))
        fit = {
            "samples": int(len(sweep_values)),
            "intercept": float(popt[1]),
            "slope": float(popt[0]),
            "std_error_intercept": float(perr[1]),
            "std_error_slope": float(perr[0]),
        }
        setattr(self, analysis_type + "_fit", fit)

    def delete_heavy_attributes(self):
        """Delete text and token data before serializing a book."""
        for attribute in ("text", "tokens", "zh_characters"):
            try:
                delattr(self, attribute)
            except AttributeError:
                pass


def mongo_connection(database, client="mongodb://localhost:27017/", collection="corpus"):
    myclient = pymongo.MongoClient(client)
    mydb = myclient[database]
    mycol = mydb[collection]
    return myclient, mydb, mycol


def insert_book_mongo(book, collection):
    collection.insert_one(json_ready(book.__dict__))


def is_book_in_mongodb(book, collection):
    try:
        myquery = {"creator": book.creator, "title": book.title}
        mydoc = collection.find_one(myquery)
        if mydoc:
            return True
        return False
    except AttributeError:
        return True


def backup_mongo(db):
    """Write a MongoDB dump for a database."""
    try:
        backup = subprocess.Popen(["mongodump", "--host", "localhost", "--db", db])
        backup.communicate()
        if backup.returncode != 0:
            sys.exit(1)
        print("Dump done for " + db)
    except OSError as ex:
        print(ex)
        print("Dump failed for " + db)


def export_mongo(db, destination):
    """Export the corpus collection as JSON."""
    try:
        backup = subprocess.Popen(
            [
                "mongoexport",
                "--host",
                "localhost",
                "--db",
                db,
                "--collection",
                "corpus",
                "-o",
                destination,
                "--jsonArray",
                "--pretty",
            ]
        )
        backup.communicate()
        if backup.returncode != 0:
            sys.exit(1)
        print("Export done for " + db)
    except OSError as ex:
        print(ex)
        print("Export failed for " + db)


def correct_dirpath(dirpath):
    if str(dirpath).endswith("/"):
        return str(dirpath)
    return str(dirpath) + "/"


def get_size(filepath, unit="M"):
    if unit == "K":
        return os.path.getsize(filepath) >> 10
    if unit == "M":
        return os.path.getsize(filepath) >> 20
    if unit == "G":
        return os.path.getsize(filepath) >> 30
    return os.path.getsize(filepath)


def analyse_file(ebookpath, my_col, samples=DEFAULT_SAMPLES, max_size_mb=DEFAULT_MAX_SIZE_MB):
    """Analyse a single EPUB and write the result to MongoDB."""
    if not str(ebookpath).lower().endswith(".epub"):
        print("Only epubs can be analysed")
        return False
    try:
        ebook = str(ebookpath)
        print("Checking if book " + ebook + " is in database")
        my_book = Book(ebookpath)
        if is_book_in_mongodb(my_book, my_col):
            return False
        if get_size(ebookpath) < max_size_mb:
            print("Reading ebook " + ebook)
            my_book = Book(ebookpath, samples=samples)
        else:
            print("Book " + ebook + " too big. Only metadata is read")
        print("Writing to database")
        insert_book_mongo(my_book, my_col)
        return True
    except (KeyError, TypeError, etree.XMLSyntaxError, ebooklib.epub.EpubException) as ex:
        print(ex)
        return False


def analyse_directory(corpus_path, db, json_export=None, samples=DEFAULT_SAMPLES, max_size_mb=DEFAULT_MAX_SIZE_MB):
    """Analyze EPUB files in a directory and populate a MongoDB database."""
    books_analyzed = 0
    my_client, __, my_col = mongo_connection(db)
    for dirpath, __, files in os.walk(corpus_path):
        for ebook in files:
            result = analyse_file(correct_dirpath(dirpath) + ebook, my_col, samples, max_size_mb)
            if result:
                books_analyzed += 1
                print("Books analysed: " + str(books_analyzed))
            if json_export and books_analyzed and books_analyzed % 25 == 0:
                print("Performing export")
                export_mongo(db, json_export)
    if json_export:
        print("Performing final export")
        export_mongo(db, json_export)
    print("Closing db")
    my_client.close()


def iter_epub_files(paths):
    for input_path in paths:
        path = Path(input_path).expanduser()
        if path.is_file():
            if path.suffix.lower() == ".epub":
                yield path
            continue
        if path.is_dir():
            for epub_path in sorted(path.rglob("*")):
                if epub_path.is_file() and epub_path.suffix.lower() == ".epub":
                    yield epub_path


def analyse_epub_file(ebookpath, samples=DEFAULT_SAMPLES, max_size_mb=DEFAULT_MAX_SIZE_MB):
    """Analyse an EPUB and return a JSON-serializable record."""
    path = Path(ebookpath).expanduser()
    record = {
        "analysis_version": ANALYSIS_VERSION,
        "filepath": str(path),
        "filename": path.name,
        "status": "ok",
    }
    try:
        size_bytes = path.stat().st_size
        record["file_size_bytes"] = size_bytes
        size_mb = size_bytes / (1024 * 1024)
        if size_mb < max_size_mb:
            book = Book(str(path), samples=samples)
        else:
            book = Book(str(path))
            record["status"] = "metadata_only"
            record["reason"] = "file larger than max-size-mb"
        record.update(json_ready(book.__dict__))
        return record
    except Exception as ex:  # noqa: BLE001 - batch processing must retain per-file failures.
        record["status"] = "error"
        record["error_type"] = type(ex).__name__
        record["error"] = str(ex)
        return record


def processed_filepaths(output_path):
    processed = set()
    if not output_path.exists():
        return processed
    with output_path.open("r", encoding="utf-8") as records:
        for line in records:
            try:
                filepath = json.loads(line).get("filepath")
            except json.JSONDecodeError:
                continue
            if filepath:
                processed.add(filepath)
    return processed


def analyse_paths_to_jsonl(
    input_paths,
    output,
    samples=DEFAULT_SAMPLES,
    max_size_mb=DEFAULT_MAX_SIZE_MB,
    jobs=1,
    resume=True,
    progress_every=25,
):
    """Analyze EPUB files and stream one JSON object per line."""
    output_path = Path(output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    files = []
    seen = set()
    skipped = processed_filepaths(output_path) if resume else set()
    for epub_path in iter_epub_files(input_paths):
        filepath = str(epub_path)
        if filepath in seen or filepath in skipped:
            continue
        seen.add(filepath)
        files.append(epub_path)

    total = len(files)
    written = 0
    errors = 0
    mode = "a" if resume else "w"
    print(f"Found {total} EPUB files to process")
    with output_path.open(mode, encoding="utf-8") as records:
        if jobs > 1 and total > 1:
            with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as executor:
                futures = [
                    executor.submit(analyse_epub_file, str(path), samples, max_size_mb)
                    for path in files
                ]
                for future in concurrent.futures.as_completed(futures):
                    record = future.result()
                    records.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                    records.flush()
                    written += 1
                    errors += int(record.get("status") == "error")
                    if written % progress_every == 0 or written == total:
                        print(f"Processed {written}/{total} EPUB files")
        else:
            for path in files:
                record = analyse_epub_file(str(path), samples, max_size_mb)
                records.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                records.flush()
                written += 1
                errors += int(record.get("status") == "error")
                if written % progress_every == 0 or written == total:
                    print(f"Processed {written}/{total} EPUB files")
    return {"total": total, "written": written, "errors": errors, "output": str(output_path)}


def build_parser():
    parser = argparse.ArgumentParser(description="Analyze readability metrics for EPUB books.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-c", "--corpus-dir", type=str, help="directory containing EPUB files")
    group.add_argument("-b", "--book", type=str, help="single EPUB file to analyze")
    parser.add_argument("paths", nargs="*", help="EPUB files or directories to analyze")
    parser.add_argument("-j", "--json", "--output", dest="output", default="results/readability-results.jsonl")
    parser.add_argument("-d", "--database", type=str, help="MongoDB database for the legacy backend")
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLES)
    parser.add_argument("--max-size-mb", type=float, default=DEFAULT_MAX_SIZE_MB)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--no-resume", action="store_true", help="overwrite output instead of appending missing files")
    parser.add_argument("--fail-on-error", action="store_true", help="return a non-zero exit code if any file fails")
    return parser


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    elif argv and str(argv[0]).endswith(".py"):
        argv = argv[1:]

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.book:
        input_paths = [args.book]
    elif args.corpus_dir:
        input_paths = [args.corpus_dir]
    else:
        input_paths = args.paths

    if not input_paths:
        parser.error("provide --book, --corpus-dir, or one or more paths")

    if args.database:
        if args.book:
            __, __, my_col = mongo_connection(args.database)
            return 0 if analyse_file(args.book, my_col, args.samples, args.max_size_mb) else 1
        if args.corpus_dir:
            analyse_directory(args.corpus_dir, args.database, args.output, args.samples, args.max_size_mb)
            return 0
        parser.error("the MongoDB backend requires --book or --corpus-dir")

    summary = analyse_paths_to_jsonl(
        input_paths,
        args.output,
        samples=args.samples,
        max_size_mb=args.max_size_mb,
        jobs=max(1, args.jobs),
        resume=not args.no_resume,
    )
    print(
        "Wrote {written} records to {output} ({errors} errors)".format(
            written=summary["written"],
            output=summary["output"],
            errors=summary["errors"],
        )
    )
    if args.fail_on_error and summary["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    main()
