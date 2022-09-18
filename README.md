# Wiktionary
These are scripts written to operate on Wiktionary data, with some of their outputs.

## Raw data
The raw files available publicly at [Wikimedia Downloads](https://dumps.wikimedia.org/) are larger than GitHub's default upload limit of 2 GiB, so I have not included them here. If you want to download them yourself, the file names you should look for are `pages-meta-current.xml` (which contains the current text content of all pages) and `categorylinks.sql` (which indicates which pages are in which categories).

## Overview
### Terminology
* *pages file*: This is what I call the XML files in the data dumps like `pages-meta-current.xml` and `stub-meta-current.xml` that contain information about Wiktionary pages.

### `ns.py`
#### Purpose
To take a pages file and find all the pages in it that are in a particular namespace.

#### File inputs
1. A pages file.

#### Output
Another XML file containing only the pages in the specified namespace (and any other non-page data).

### `lang.py`
#### Purpose
To take a pages file containing mainspace pages (in other words the actual dictionary entries that contain definitions), and collect only the definitions for one language (defaults to English) from them.

#### File inputs
1. A pages file.

#### Output
Another pages file containing only the pages that had a section for the language specified, with all other language sections omitted.

### Title, namespace, ID filter
#### Purpose
To create trimmed-down copies of pages files that only contain the titles, namespaces, and IDs of the original.

#### Implementation
Rather than a Python program, I just used grep to achieve this:
```bash
grep -E '^\s{,4}(<mediawiki|</mediawiki>|<page|</page>|<title|<ns|<id)' input.xml > output.xml
```
I've only tested this on [Debian](https://en.wikipedia.org/wiki/Debian).

### `parseCats.py`
#### Purpose
To make it easier for other programs to work with Wiktionary's categories.

#### File inputs
1. The SQL file named "categorylinks.sql" in the data dumps.
1. An XML file containing title / id associations for all pages (including categories). The file named "pages-meta-current.xml" in the dumps fulfills these criteria, but mostly consists of other data that would be irrelevant here. It is suggested one use the title, namespace, id filter on "pages-meta-current.xml" and give the result to `parseCats.py`.

#### Output
A CSV file containing a line for every category-page association. Each line consists of the category ID, the category name (without the "Category:" prefix), the page ID, and the page name (with any appropriate namespace prefix). As an example, the first few lines created from a data dump made in 2022-06 were:

```csv
227906,Wiktionary beginners,6,Wiktionary:Welcome, newcomers
303568,Wiktionary pages with shortcuts,6,Wiktionary:Welcome, newcomers
90507,Wiktionary,8,Wiktionary:Text of the GNU Free Documentation License
```

### `deepCatFilter.py`
#### Purpose
To allow one to create lists of terms based on what categories they are in. For example, say you wanted a list of all English multiword terms that are in full modern use. More specifically, you want all terms that are

* in [Category:English multiword terms](https://en.wiktionary.org/wiki/Category:English multiword terms)
* and not in any of
   * [Category:English dated terms](https://en.wiktionary.org/wiki/Category:English dated terms)
   * [Category:English archaic terms](https://en.wiktionary.org/wiki/Category:English archaic terms)
   * [Category:English obsolete terms](https://en.wiktionary.org/wiki/Category:English obsolete terms)
`deepCatFilter.py` can do this for you.

#### File inputs
1. A parsed categories CSV file as created by `parseCats.py`.

#### Output
A list of all the terms that meet the criteria, one per line, in an output file.
