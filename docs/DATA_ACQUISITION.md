# Data acquisition and OCR conversion

## Printed source

The source was a lawfully acquired physical copy of the nine-volume 2nd edition of *Zhongyi Fangji Da Cidian*. Pages were photographed and assembled into PDF files for research use.

## PDF-to-Markdown conversion

The PDFs were processed with MinerU through the OpenDataLab PDF Extractor:

<https://opendatalab.com/OpenSourceTools/Extractor/PDF>

MinerU was selected for the established conversion because its Markdown output retained line breaks, bracketed field headings, and embedded table and image markers used by the record parser. The study did not compare OCR engines and does not claim that this conversion route is superior to newer OCR or vision-language systems.

## Access boundary

The photographed pages, PDFs, and complete OCR-derived Markdown remain restricted because they substantially reproduce a copyrighted third-party book. The public package instead provides derived benchmark indices, paired and adjudicated labels, model predictions, binary field outcomes, aggregate tables, and analysis code. Researchers with lawful access to the same edition can generate a local OCR layer and apply the released parser and evaluation scripts.
