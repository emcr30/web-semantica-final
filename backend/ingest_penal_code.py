"""
Script to ingest Peruvian Penal Code (Código Penal Peruano)
Structures the Penal Code into RDF/TTL format with proper relationships

Usage:
    python -m backend.ingest_penal_code
    
This will create Ontologia/legal_working.ttl with penal code articles
"""

import os
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, DCTERMS, XSD

# Penal Code Data Structure - CÓDIGO PENAL PERUANO (D.L. 635)
PENAL_CODE_ARTICLES = [
    # BOOK I - GENERAL PART / PARTE GENERAL
    {"numero": "1", "titulo": "Principio de legalidad", "texto": "Nadie será sancionado por un acto no previsto como delito o falta por la ley vigente al momento de su comisión, ni sometido a pena o medida de seguridad que no estén establecidas en ella.", "libro": "Primero", "titulo_libro": "DISPOSICIONES GENERALES", "capitulo": "1", "titulo_capitulo": "Principio de Legalidad", "tipo": "Artículo"},
    {"numero": "2", "titulo": "Irretroactividad de la ley penal", "texto": "La ley penal aplicable es la vigente al momento de la comisión del delito. Sin embargo, se aplicará la ley posterior si es más favorable al reo.", "libro": "Primero", "titulo_libro": "DISPOSICIONES GENERALES", "capitulo": "1", "titulo_capitulo": "Principio de Legalidad", "tipo": "Artículo"},
    {"numero": "3", "titulo": "Ambito de validez espacial", "texto": "La ley penal peruana se aplica: 1. Por delitos cometidos en el territorio de la República. 2. Por delitos cometidos a bordo de naves o aeronaves peruanas. 3. En los demás casos establecidos por las normas de Derecho Internacional.", "libro": "Primero", "titulo_libro": "DISPOSICIONES GENERALES", "capitulo": "2", "titulo_capitulo": "Ambito de Validez", "tipo": "Artículo"},
    
    # CRIMES AGAINST LIFE / DELITOS CONTRA LA VIDA
    {"numero": "106", "titulo": "Parricidio", "texto": "El que, a sabiendas, mata a su ascendiente, descendiente, cónyuge o hermano, será punido con pena privativa de libertad no menor de quince años.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "1", "titulo_capitulo": "Delitos contra la vida", "pena_minima": 15, "pena_unidad": "años"},
    {"numero": "107", "titulo": "Homicidio simple", "texto": "El que mata a otro será punido con pena privativa de libertad no menor de seis ni mayor de veinte años.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "1", "titulo_capitulo": "Delitos contra la vida", "pena_minima": 6, "pena_maxima": 20, "pena_unidad": "años"},
    {"numero": "108", "titulo": "Homicidio calificado", "texto": "Será reprimido con pena privativa de libertad no menor de veinticinco años, el que mata a otro concurriendo cualquiera de las circunstancias siguientes: alevosía, precio remuneratorio, furor u odio, facilitar otro delito o gran crueldad.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "1", "titulo_capitulo": "Delitos contra la vida", "pena_minima": 25, "pena_unidad": "años"},
    {"numero": "109", "titulo": "Homicidio por emoción violenta", "texto": "El que mata a otro, en estado de ira o intenso dolor causado por actos injustos e inmediatos del occiso, será punido con pena privativa de libertad no menor de tres ni mayor de cinco años.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "1", "titulo_capitulo": "Delitos contra la vida", "pena_minima": 3, "pena_maxima": 5, "pena_unidad": "años"},
    {"numero": "110", "titulo": "Inducción al suicidio", "texto": "El que, deliberadamente, induce a otro al suicidio o lo ayuda a cometerlo, será reprimido con pena privativa de libertad no menor de cinco ni mayor de diez años.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "1", "titulo_capitulo": "Delitos contra la vida", "pena_minima": 5, "pena_maxima": 10, "pena_unidad": "años"},
    
    # CRIMES AGAINST BODILY INTEGRITY / DELITOS CONTRA LA INTEGRIDAD CORPORAL
    {"numero": "121", "titulo": "Lesión grave", "texto": "El que causa a otro daño grave en el cuerpo o en la salud será reprimido con pena privativa de libertad no menor de cuatro ni mayor de ocho años.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "2", "titulo_capitulo": "Delitos contra la integridad corporal", "pena_minima": 4, "pena_maxima": 8, "pena_unidad": "años"},
    {"numero": "122", "titulo": "Lesión leve", "texto": "El que causa a otro un daño en el cuerpo o en la salud que requiera más de diez días de asistencia o descanso será reprimido con pena privativa de libertad no mayor de dos años.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "2", "titulo_capitulo": "Delitos contra la integridad corporal", "pena_maxima": 2, "pena_unidad": "años"},
    
    # CRIMES AGAINST LIBERTY / DELITOS CONTRA LA LIBERTAD
    {"numero": "149", "titulo": "Violación sexual", "texto": "El que tiene acceso carnal con una persona por violencia o grave amenaza es punible con pena privativa de libertad no menor de catorce ni mayor de veinte años.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "3", "titulo_capitulo": "Delitos contra la libertad", "pena_minima": 14, "pena_maxima": 20, "pena_unidad": "años"},
    {"numero": "150", "titulo": "Violación de menor de edad", "texto": "Cuando la víctima tiene menos de catorce años, la pena será no menor de dieciséis ni mayor de veinticuatro años.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "3", "titulo_capitulo": "Delitos contra la libertad", "pena_minima": 16, "pena_maxima": 24, "pena_unidad": "años"},
    {"numero": "151", "titulo": "Actos contra el pudor", "texto": "El que, sin propósito de llegar a la cópula, ejecuta sobre otra persona un acto contra el pudor o la hace ejecutar, será reprimido con pena privativa de libertad no menor de tres ni mayor de cinco años.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "3", "titulo_capitulo": "Delitos contra la libertad", "pena_minima": 3, "pena_maxima": 5, "pena_unidad": "años"},
    {"numero": "152", "titulo": "Rapto", "texto": "El que sustrae a una persona del lugar donde la autoridad ha determinado que debe permanecer será reprimido con pena privativa de libertad no menor de dos ni mayor de cuatro años.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "3", "titulo_capitulo": "Delitos contra la libertad", "pena_minima": 2, "pena_maxima": 4, "pena_unidad": "años"},
    {"numero": "153", "titulo": "Sustracción de menores", "texto": "El que sustrae a un menor de dieciocho años del lugar donde la autoridad lo ha puesto será reprimido con pena privativa de libertad no menor de dos ni mayor de cuatro años.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "3", "titulo_capitulo": "Delitos contra la libertad", "pena_minima": 2, "pena_maxima": 4, "pena_unidad": "años"},
    
    # CRIMES AGAINST PROPERTY / DELITOS CONTRA EL PATRIMONIO
    {"numero": "185", "titulo": "Hurto", "texto": "El que sustrae un bien mueble, total o parcialmente ajeno, para aprovecharse ilícitamente del mismo, sustrayéndolo del lugar en que se encuentra, será reprimido con pena privativa de libertad no menor de uno ni mayor de tres años.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "5", "titulo_capitulo": "Delitos contra el patrimonio", "pena_minima": 1, "pena_maxima": 3, "pena_unidad": "años"},
    {"numero": "186", "titulo": "Hurto agravado", "texto": "La pena será no menor de tres ni mayor de seis años si el hurto es cometido: en casa habitada, durante la noche, en lugar desolado, mediante destreza o artificios, o con destrozo del bien.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "5", "titulo_capitulo": "Delitos contra el patrimonio", "pena_minima": 3, "pena_maxima": 6, "pena_unidad": "años"},
    {"numero": "188", "titulo": "Robo", "texto": "El que se apodera ilícitamente de un bien mueble, empleando violencia contra la persona o amenazándola con un peligro inminente para su vida o integridad física, será reprimido con pena privativa de libertad no menor de tres ni mayor de ocho años.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "5", "titulo_capitulo": "Delitos contra el patrimonio", "pena_minima": 3, "pena_maxima": 8, "pena_unidad": "años"},
    {"numero": "189", "titulo": "Robo agravado", "texto": "La pena será no menor de cinco ni mayor de quince años si el robo es cometido: en casa habitada, durante la noche, a mano armada, en lugar desolado o en vía pública.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "5", "titulo_capitulo": "Delitos contra el patrimonio", "pena_minima": 5, "pena_maxima": 15, "pena_unidad": "años"},
    {"numero": "196", "titulo": "Estafa", "texto": "El que, mediante engaño, procura para sí o para otro un provecho ilícito en perjuicio ajeno será reprimido con pena privativa de libertad no menor de uno ni mayor de tres años.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "5", "titulo_capitulo": "Delitos contra el patrimonio", "pena_minima": 1, "pena_maxima": 3, "pena_unidad": "años"},
    {"numero": "200", "titulo": "Apropiación ilícita", "texto": "El que, en su calidad de depositario o por otra razón contractual, tiene obligación de custodiar o administrar bienes ajenos, se apropie de éstos o los distraiga será reprimido con pena privativa de libertad no menor de dos ni mayor de cuatro años.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "5", "titulo_capitulo": "Delitos contra el patrimonio", "pena_minima": 2, "pena_maxima": 4, "pena_unidad": "años"},
    
    # CRIMES AGAINST HONOR / DELITOS CONTRA EL HONOR
    {"numero": "131", "titulo": "Injuria", "texto": "El que ofende el honor, la reputación o la dignidad de una persona es punible con pena privativa de libertad no mayor de un año o con sesenta días multa.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "4", "titulo_capitulo": "Delitos contra el honor", "pena_maxima": 1, "pena_unidad": "años"},
    {"numero": "132", "titulo": "Difamación", "texto": "El que, ante terceros, imputa a una persona la comisión de un hecho delictuoso que afecta su honor, siendo la imputación falsa, es punible con pena privativa de libertad no mayor de un año o con ciento veinte días multa.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "4", "titulo_capitulo": "Delitos contra el honor", "pena_maxima": 1, "pena_unidad": "años"},
    
    # CRIMES AGAINST PUBLIC ADMINISTRATION / DELITOS CONTRA LA ADMINISTRACIÓN PÚBLICA
    {"numero": "376", "titulo": "Fraude procesal", "texto": "El que, siendo parte en un proceso o tercero, presenta documentos falsos, propone testigos falsos o propone peritos falsos será reprimido con pena privativa de libertad no menor de dos ni mayor de seis años.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "22", "titulo_capitulo": "Delitos contra la administración pública", "pena_minima": 2, "pena_maxima": 6, "pena_unidad": "años"},
    {"numero": "397", "titulo": "Cohecho pasivo", "texto": "El funcionario o servidor público que, directa o indirectamente, solicita, acepta o recibe dinero, bienes o cualquier otra ventaja o promesa, para realizar, retardar u omitir un acto de su función será reprimido con pena privativa de libertad no menor de cinco ni mayor de quince años.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "22", "titulo_capitulo": "Delitos contra la administración pública", "pena_minima": 5, "pena_maxima": 15, "pena_unidad": "años"},
    {"numero": "398", "titulo": "Cohecho activo", "texto": "El que ofrece, promete o da dinero, bienes o cualquier otra ventaja al funcionario o servidor público será reprimido con pena privativa de libertad no menor de tres ni mayor de diez años.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "22", "titulo_capitulo": "Delitos contra la administración pública", "pena_minima": 3, "pena_maxima": 10, "pena_unidad": "años"},
    {"numero": "399", "titulo": "Malversación de fondos públicos", "texto": "El funcionario o servidor público que apropia, sustrae o consume en su provecho fondos o bienes públicos será reprimido con pena privativa de libertad no menor de cinco ni mayor de quince años.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "22", "titulo_capitulo": "Delitos contra la administración pública", "pena_minima": 5, "pena_maxima": 15, "pena_unidad": "años"},
    {"numero": "400", "titulo": "Peculado", "texto": "El funcionario o servidor público que, en ejercicio de sus funciones, se apropia de bienes del Estado será reprimido con pena privativa de libertad no menor de cinco ni mayor de diez años.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "22", "titulo_capitulo": "Delitos contra la administración pública", "pena_minima": 5, "pena_maxima": 10, "pena_unidad": "años"},
    
    # CRIMES AGAINST PUBLIC FAITH / DELITOS CONTRA LA FE PÚBLICA
    {"numero": "427", "titulo": "Falsificación de documentos públicos", "texto": "El que falsifica, altera o falsifica la firma de un documento público será reprimido con pena privativa de libertad no menor de tres ni mayor de diez años.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "23", "titulo_capitulo": "Delitos contra la fe pública", "pena_minima": 3, "pena_maxima": 10, "pena_unidad": "años"},
    {"numero": "428", "titulo": "Falsificación de documentos privados", "texto": "El que falsifica, altera o falsifica un documento privado será reprimido con pena privativa de libertad no menor de dos ni mayor de seis años.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "23", "titulo_capitulo": "Delitos contra la fe pública", "pena_minima": 2, "pena_maxima": 6, "pena_unidad": "años"},
    
    # CRIMES AGAINST PUBLIC ORDER / DELITOS CONTRA EL ORDEN PÚBLICO
    {"numero": "337", "titulo": "Incumplimiento de deberes", "texto": "El que infringe las normas establecidas por ley o sentencia, por causa justificada o sin ella, será reprimido con pena privativa de libertad no mayor de un año o con sesenta días multa.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "20", "titulo_capitulo": "Delitos contra el orden público", "pena_maxima": 1, "pena_unidad": "años"},
    {"numero": "338", "titulo": "Desorden público", "texto": "El que mediante tumulto o golpes causa disturbios en lugares públicos será reprimido con pena privativa de libertad no mayor de un año.", "libro": "Segundo", "titulo_libro": "DELITOS", "capitulo": "20", "titulo_capitulo": "Delitos contra el orden público", "pena_maxima": 1, "pena_unidad": "años"},
]

def create_penal_code_rdf():
    """
    Creates RDF graph with Penal Code articles
    """
    # Namespaces
    lo = Namespace("http://legalontosystem.pe/ontology#")
    LKIF = "http://www.estrellaproject.org/lkif-core/legal-rule.owl#"
    # Use ELI URIs for Código Penal (1991)
    ELI_BASE = "https://leyes.peru/eli/1991/codigo-penal"
    
    graph = Graph()
    graph.bind('lo', lo)
    graph.bind('eli', URIRef("https://leyes.peru/eli/1991/codigo-penal"))
    graph.bind('dcterms', DCTERMS)
    graph.bind('rdfs', RDFS)
    graph.bind('rdf', RDF)
    
    # Create main Penal Code resource
    codigo_penal = URIRef(ELI_BASE)
    graph.add((codigo_penal, RDF.type, lo.Ley))
    graph.add((codigo_penal, lo.titulo, Literal("Código Penal Peruano")))
    graph.add((codigo_penal, lo.numero, Literal("CP")))
    graph.add((codigo_penal, DCTERMS.issued, Literal("1991-04-08")))
    graph.add((codigo_penal, DCTERMS.description, 
               Literal("Código Penal Peruano - Decreto Legislativo N° 635")))
    graph.add((codigo_penal, lo.jurisdiccion, Literal("Perú")))
    graph.add((codigo_penal, lo.estado, Literal("vigente")))

    # Create a Version instance for the 1991 edition
    version_year = "1991"
    version_uri = URIRef(f"{ELI_BASE}/version/{version_year}")
    graph.add((version_uri, RDF.type, lo.Version))
    graph.add((version_uri, lo.versionYear, Literal(version_year, datatype=XSD.gYear)))
    # point to the source law document/resource
    graph.add((version_uri, lo.sourceDocument, codigo_penal))
    
    # Add articles
    for article in PENAL_CODE_ARTICLES:
        art_num = article["numero"]
        art_uri = URIRef(f"{ELI_BASE}/articulo/{art_num}")
        
        # Create Article
        graph.add((art_uri, RDF.type, lo.Articulo))
        # Add LKIF type for legal rule/article
        try:
            graph.add((art_uri, RDF.type, URIRef(LKIF + 'LegalRule')))
        except Exception:
            pass
        graph.add((art_uri, lo.numero, Literal(art_num, datatype='http://www.w3.org/2001/XMLSchema#int')))
        graph.add((art_uri, lo.titulo, Literal(article["titulo"])))
        graph.add((art_uri, lo.contenido, Literal(article["texto"])))
        
        # Metadata
        graph.add((art_uri, lo.libro, Literal(article.get("libro", "N/A"))))
        graph.add((art_uri, lo.capitulo, Literal(article.get("capitulo", "N/A"))))
        graph.add((art_uri, lo.titulo_capitulo, Literal(article.get("titulo_capitulo", "N/A"))))
        
        # Penalties if applicable
        if "pena_minima" in article:
            pena_text = f"No menor de {article['pena_minima']}"
            if "pena_maxima" in article:
                pena_text += f" ni mayor de {article['pena_maxima']}"
            pena_text += f" {article.get('pena_unidad', '')}"
            graph.add((art_uri, lo.pena, Literal(pena_text)))
        
        # Relate to Penal Code (add both property variants for compatibility)
        graph.add((art_uri, lo.perteneceA, codigo_penal))
        graph.add((codigo_penal, lo.contiene, art_uri))
        # Also add ontology-standard relations used elsewhere: esParteDe / tieneArticulo
        graph.add((art_uri, lo.esParteDe, codigo_penal))
        graph.add((codigo_penal, lo.tieneArticulo, art_uri))
        # Link article to specific Version (per new versioning model)
        graph.add((version_uri, lo.hasArticle, art_uri))
        graph.add((art_uri, lo.belongsTo, version_uri))
        graph.add((art_uri, lo.articleNumber, Literal(art_num, datatype=XSD.integer)))
        # Add a rdfs:label for better search compatibility
        graph.add((art_uri, RDFS.label, Literal(f"Artículo {art_num}: {article.get('titulo','')}")))
    
    return graph

def save_penal_code_ttl(output_path=None):
    """
    Generates and saves Penal Code RDF as TTL file
    
    Args:
        output_path: where to save (default: Ontologia/legal_working.ttl)
    """
    if output_path is None:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        output_path = os.path.join(base_dir, 'Ontologia', 'legal_working.ttl')
    
    print(f"📜 Generating Penal Code RDF graph...")
    graph = create_penal_code_rdf()
    
    print(f"💾 Saving to {output_path}...")
    graph.serialize(destination=output_path, format='turtle')
    
    print(f"✅ Penal Code saved!")
    print(f"   Articles: {len(PENAL_CODE_ARTICLES)}")
    print(f"   File: {output_path}")
    print(f"   Size: {len(graph)} triples")
    
    return output_path

if __name__ == '__main__':
    save_penal_code_ttl()
