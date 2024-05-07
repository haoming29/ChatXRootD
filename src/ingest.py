import logging
import os
import re
from typing import List

from bs4 import BeautifulSoup

from langchain_core.documents import Document
from langchain_community.document_loaders import RecursiveUrlLoader
from langchain_community.vectorstores import FAISS
from langchain.utils.html import PREFIXES_TO_IGNORE_REGEX
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
)
from parse import xrootd_docs_extractor
from constant import SUFFIXES_TO_IGNORE_REGEX, HEADERS_TO_SPLIT_ON

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def metadata_extractor(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    title = soup.find("title")
    description = soup.find("meta", attrs={"name": "description"})
    html = soup.find("html")

    title_paragraphs = soup.find_all("p", class_="StylePalatino24ptBoldCentered")
    doc_metas = soup.find_all("p", class_="StylePalatino10ptBoldCentered")

    real_title = "XrootD "
    release_date = ""
    software_version = ""
    author = ""
    # Loop through the found elements and print their text if they are not empty
    for p in title_paragraphs:
        if p.text.strip() and not p.text.strip().isspace():
            real_title += p.text.strip()

    doc_meta_ct = 0
    for p in doc_metas:
        if p.text.strip() and not p.text.strip().isspace():
            if doc_meta_ct == 0:
                release_date = p.text.strip()
            elif doc_meta_ct == 1:
                software_version = p.text.strip()
            elif doc_meta_ct == 2:
                author = p.text.strip()
            doc_meta_ct += 1

    h1_tag = soup.find("h1")
    introduction = ""
    if h1_tag is not None:
        # Find the first non-empty <p> following the <h1>
        current_tag = h1_tag.find_next_sibling()

        while current_tag:
            if current_tag.name == "p" and current_tag.text.strip():
                break
            current_tag = current_tag.find_next_sibling()

        introduction = current_tag.text.strip() if current_tag is not None else ""

    return {
        "source": url,
        "title": real_title if title else title.get_text() if title else "",
        "documentation_release_date": release_date,
        "xrootd_software_version": software_version,
        "documentation_author": author,
        "description": (
            introduction
            if introduction
            else description.get("content", "") if description else ""
        ),
        "language": html.get("lang", "") if html else "en",
    }


def simple_extractor(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    # List of classes to remove
    classes_to_remove = ["MsoToc1", "MsoToc2", "MsoToc3", "MsoToc4"]

    # Find and decompose all <p> elements with specified classes
    for class_name in classes_to_remove:
        for element in soup.find_all("p", class_=class_name):
            element.decompose()

    return re.sub(r"[\s]*\n+[\s]*", "\n", soup.text).strip().replace("\xa0", "")


def load_xrootd_docs() -> List[Document]:
    loader = RecursiveUrlLoader(
        url="https://xrootd.slac.stanford.edu/docs.html",
        max_depth=2,
        metadata_extractor=metadata_extractor,
        prevent_outside=True,
        use_async=False,
        timeout=600,
        base_url="https://xrootd.slac.stanford.edu/",
        # Drop trailing / to avoid duplicate pages.
        link_regex=(
            f"href=[\"']{PREFIXES_TO_IGNORE_REGEX}((?:{SUFFIXES_TO_IGNORE_REGEX}.)*?)"
            r"(?:[\#'\"]|\/[\#'\"])"
        ),
        extractor=xrootd_docs_extractor,
        check_response_status=True,
    )

    return loader.load()


def ingest_docs():
    docs = load_xrootd_docs()
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT_ON, strip_headers=False
    )
    md_header_splits = markdown_splitter.split_text(docs[0].page_content)
    for split in md_header_splits:
        split.metadata = docs[0].metadata | split.metadata

    table_splits: List[Document] = []
    for md_doc in md_header_splits:
        splitted = re.split(re.escape("[table]"), md_doc.page_content)
        for split in splitted:
            new_doc = Document(page_content=split, metadata=md_doc.metadata.copy())
            table_splits.append(new_doc)

    text_splitter = RecursiveCharacterTextSplitter(chunk_overlap=400)
    final_splits = text_splitter.split_documents(table_splits)

    vectorstore = FAISS.from_documents(
        documents=final_splits, embedding=OpenAIEmbeddings()
    )

    logger.info(f"FAISS now have {vectorstore.index.nbtotal} vectors")
    vectorstore.save_local("./faiss.store")


if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        logger.error("Environment variable OPENAI_API_KEY is required")
        exit(1)
    ingest_docs()
