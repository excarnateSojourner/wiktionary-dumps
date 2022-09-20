# Rhymes
For the context of why I wrote this, see [User:ExcarnateSojourner/Terms lacking rhymes](https://en.wiktionary.org/wiki/User:ExcarnateSojourner/Terms_lacking_rhymes).

## pronLines.txt
To generate pronLines.txt, use:

```bash
grep -ioP '(?<=\{\{IPA\|en\|).*?(?=\}\})' pages-ns0-en.xml | sed 's/[.ˌ() ͡]//g' > pronLines.txt
```
