# Extracting text from PDFs
In general, there is no "perfect" way to extract text from a PDF. Typically the text is extracted in the order of height and then width (i.e. from top left to bottom right). In this repo, the same rule is used + when two lines are identified to be on the same height, they are separated with a tab (\t).

## Extracting text from a digital/searchable PDF
In this case, no OCR is needed and the text can be straightaway extracted. See [extract_text_digital.ipynb](extract_text_digital.ipynb) on how this repo deals with digital PDFs.

## Extracting text from a scan PDF
Scans do not have a text layer. Thus, the text cannot be simply extracted from the PDF. To get the text from the scan (which is an image), Optical Character Recognition needs to be performed. Afterwhich, the text can be extracted in a similar way to the digital/searchable pdf.
See [extract_text_scan.ipynb](extract_text_scan.ipynb) on how this repo deals with scan PDFs.