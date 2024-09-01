# Wiktionary
These are scripts written to operate on data from [Wiktionary](https://en.wiktionary.org/wiki/Wiktionary:Main_Page), a free online dictionary.

## Raw data
The raw files available publicly at [Wikimedia Downloads](https://dumps.wikimedia.org/) are larger than GitHub's default upload limit of 2 GiB, so I have not included them here.

## Overview
The database dump files that these scripts parse are in XML and SQL format. I use the term ***pages file*** to refer to the XML files such as `pages-meta-current.xml` and `stub-meta-current.xml` that contain information about Wiktionary pages.

### `ns`
#### Purpose
To take a pages file and select all the pages in it that are in a particular namespace.

#### File inputs
1. A pages file.

#### Output
Another XML file containing only the pages in the specified namespace (and any other non-page data).

### `lang`
#### Purpose
To take a pages file containing pages in Wiktionary's main namespace (in other words the actual dictionary entries that contain definitions), and collect only the definitions for one language (defaults to English) from them.

#### File inputs
1. A pages file.

#### Output
Another pages file containing only the pages that had a section for the language specified, with all other language sections omitted.

### `parse_stubs`
#### Purpose
To convert a pages file such as `stub-meta-current.xml` to a CSV file containing the ids, Wiktionary namespaces, and titles of Wiktionary pages.

#### File inputs
1. The pages file containing stubs (i.e. ids, namespaces, and titles). The best file for this in the dumps is `stub-meta-current.xml` (but `pages-meta-current.xml` should also work).

#### Output
A CSV file in which each line consists of the id, namespace, and title of a page, separated by vertical bars (`|`). For example, here are a few of the first lines created from a data dump made in 2024-01 (with some similar lines removed):
```csv
6|4|Wiktionary:Welcome, newcomers
9|2|User:Sjc~enwiktionary
12|4|Wiktionary:What Wiktionary is not
15|3|User talk:Merphant
16|0|dictionary
19|0|free
20|0|thesaurus
```

### `parse_redirects`
#### Purpose
To convert redirect data from SQL to CSV to make it easier for other programs to work with.

#### File inputs
1. The SQL file named `redirect.sql` in the database dumps.
1. A CSV file containing stubs, as created by `parse_stubs`.
1. A pages file containing the ids and titles of Wiktionary's namespaces. Any of the pages files in the database dumps will work, but not after they have gone through `ns`.

#### Output
A CSV file containing redirect data. Each line gives a source page id, source page title, destination page id, and destination page title, all separated by vertical bars (`|`).

### `parse_cats`
#### Purpose
To convert category membership data from SQL to CSV to make it easier for other programs to work with Wiktionary's categories.

#### File inputs
1. The SQL file named `categorylinks.sql` in the data dumps.
1. A CSV file containing stubs, as produced by `parse_stubs`.

#### Output
A CSV file containing a line for every category-page association. Each line consists of the category ID, the category name (without the "Category:" prefix), the page ID, and the page name (with any appropriate Wiktionary namespace prefix), separated by vertical bars. As an example, the first few lines created from a data dump made in 2022-06 were:

```csv
227906|Wiktionary beginners|6|Wiktionary:Welcome, newcomers
303568|Wiktionary pages with shortcuts|6|Wiktionary:Welcome, newcomers
90507|Wiktionary|8|Wiktionary:Text of the GNU Free Documentation License
```

### `find_terms`
#### Purpose
To allow one to create lists of terms based on what categories they are in, what labels they have, what templates they use, what parts of speech they are, and / or whether they match a regex. For example, say you wanted a list of English nouns used in physics that consisted only of lowercase English letters, excluding any that are not used much anymore. `find_terms` can do this for you.

#### File inputs
1. A pages file containing at least those terms in the included categories.
1. A CSV file describing category memberships as created by `parse_cats`.
1. A CSV file containing redirect data, as created by `parse_redirects`.

#### Output
A list of all the terms that meet the criteria, one per line, in an output file.

## Windows
I have sometimes found it necessary on Windows to run Python like this:

`python -u -X utf8 script.py --script-options`

* `-u` ensures output is unbuffered. If I don't use this I find the verbose output of these scripts can get buffered until I kill Python, thinking it has frozen. Even with this option, I sometimes find I get more output if I hit Enter every so often.
* `-X utf8` ensures output is always in UTF-8, even when stdout is being piped to another command in Command Prompt.
