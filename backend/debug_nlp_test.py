from backend import nlp_extractor
import re
text = "El 15 de marzo de 2023, en el distrito de Cayma (Arequipa). Juan Pérez atacó con un cuchillo a Luis Ramos, causándole la muerte inmediata. De acuerdo con los testigos, se trató de una pelea originada por una discusión previa y no existió planificación previa. La familia de la víctima interpuso denuncia al día siguiente."
print('TEXT:', text)
print('\nChecking KEYWORD_PATTERNS:')
for p in nlp_extractor.KEYWORD_PATTERNS:
    m = re.findall(p, text, re.IGNORECASE)
    print(p, '->', m)
print('\nCRIME_RE ->', nlp_extractor.CRIME_RE.findall(text))
print('MORTALITY_RE ->', nlp_extractor.MORTALITY_RE.findall(text))
print('\nextract_entities result:')
print(nlp_extractor.extract_entities(text))
print('\nextract_case_metadata result:')
print(nlp_extractor.extract_case_metadata(text))
