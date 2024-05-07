import re
from typing import Generator

from bs4 import BeautifulSoup, Doctype, NavigableString, Tag


def xrootd_docs_extractor(html: str) -> str:
    """Source https://github.com/langchain-ai/chat-langchain/blob/master/backend/parser.py"""
    soup = BeautifulSoup(html, "lxml")
    # Remove all the tags that are not meaningful for the extraction.
    SCAPE_TAGS = ["nav", "footer", "aside", "script", "style"]
    [tag.decompose() for tag in soup.find_all(SCAPE_TAGS)]

    classes_to_remove = ["MsoToc1", "MsoToc2", "MsoToc3", "MsoToc4"]

    # Find and decompose all <p> elements with specified classes
    for class_name in classes_to_remove:
        for element in soup.find_all("p", class_=class_name):
            element.decompose()

    def get_text(tag: Tag) -> Generator[str, None, None]:
        for child in tag.children:
            if isinstance(child, Doctype):
                continue

            if isinstance(child, NavigableString):
                yield child
            elif isinstance(child, Tag):
                if child.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                    yield f"{'#' * int(child.name[1:])} {child.get_text()}\n\n"
                elif child.name == "a":
                    yield f"[{child.get_text(strip=False)}]({child.get('href')})"
                elif child.name == "img":
                    yield f"![{child.get('alt', '')}]({child.get('src')})"
                elif child.name in ["strong", "b"]:
                    yield f"**{child.get_text(strip=False)}**"
                elif child.name in ["em", "i"]:
                    yield f"_{child.get_text(strip=False)}_"
                elif child.name == "br":
                    yield "\n"
                elif child.name == "code":
                    parent = child.find_parent()
                    if parent is not None and parent.name == "pre":
                        classes = parent.attrs.get("class", "")

                        language = next(
                            filter(lambda x: re.match(r"language-\w+", x), classes),
                            None,
                        )
                        if language is None:
                            language = ""
                        else:
                            language = language.split("-")[1]

                        lines: list[str] = []
                        for span in child.find_all("span", class_="token-line"):
                            line_content = "".join(
                                token.get_text() for token in span.find_all("span")
                            )
                            lines.append(line_content)

                        code_content = "\n".join(lines)
                        yield f"```{language}\n{code_content}\n```\n\n"
                    else:
                        yield f"`{child.get_text(strip=False)}`"

                elif child.name == "p":
                    yield from get_text(child)
                    yield "\n\n"
                elif child.name == "ul":
                    for li in child.find_all("li", recursive=False):
                        yield "- "
                        yield from get_text(li)
                        yield "\n\n"
                elif child.name == "ol":
                    for i, li in enumerate(child.find_all("li", recursive=False)):
                        yield f"{i + 1}. "
                        yield from get_text(li)
                        yield "\n\n"
                elif child.name == "div" and "tabs-container" in child.attrs.get(
                    "class", [""]
                ):
                    tabs = child.find_all("li", {"role": "tab"})
                    tab_panels = child.find_all("div", {"role": "tabpanel"})
                    for tab, tab_panel in zip(tabs, tab_panels):
                        tab_name = tab.get_text(strip=True)
                        yield f"{tab_name}\n"
                        yield from get_text(tab_panel)
                elif (
                    child.name == "div"
                    and child.attrs.get("style", "")
                    == "border:solid windowtext 1.0pt;padding:1.0pt 4.0pt 1.0pt 4.0pt"
                ):
                    # xrootd codeblock style
                    code = "".join(c.text + "\n" for c in child.contents)
                    yield f"```\n{code}\n```"
                    yield "\n\n"
                    pass
                elif child.name == "table":
                    yield "[table]"
                    thead = child.find("thead")
                    header_exists = isinstance(thead, Tag)
                    if header_exists:
                        headers = thead.find_all("th")
                        if headers:
                            yield "| "
                            yield " | ".join(header.get_text() for header in headers)
                            yield " |\n"
                            yield "| "
                            yield " | ".join("----" for _ in headers)
                            yield " |\n"

                    tbody = child.find("tbody")
                    tbody_exists = isinstance(tbody, Tag)
                    if tbody_exists:
                        for row in tbody.find_all("tr"):
                            yield "| "
                            yield " | ".join(
                                cell.get_text(strip=True) for cell in row.find_all("td")
                            )
                            yield " |\n"
                    else:
                        first_row = child.find("tr")
                        headers = first_row.find_all("td")
                        yield "| "
                        yield " | ".join(
                            header.get_text(strip=True) for header in headers
                        )
                        yield " |\n"
                        yield "| "
                        yield " | ".join("----" for _ in headers)
                        yield " |\n"
                        data_rows = first_row.find_next_siblings("tr")
                        for row in data_rows:
                            yield "| "
                            yield " | ".join(
                                cell.get_text(strip=True) for cell in row.find_all("td")
                            )
                            yield " |\n"
                    yield "\n\n[table]"
                elif child.name in ["button"]:
                    continue
                else:
                    yield from get_text(child)

    joined = (
        "".join(get_text(soup))
        .replace("\xa0", "")
        .replace("\r\n", " ")
        .replace("****", "")
    )
    return re.sub(r"\n\n+", "\n\n", joined).strip()
