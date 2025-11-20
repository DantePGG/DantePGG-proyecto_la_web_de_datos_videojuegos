# DantePGG-proyecto_la_web_de_datos_videojuegos
This is the repo for our project for the CC7220-1 course.


-----

# Análisis de Datos de Videojuegos (RDF/SPARQL)

Este repositorio contiene las consultas SPARQL desarrolladas para analizar el dataset de ventas de videojuegos (`videogames_with_wikidata.ttl`), combinando datos locales con información de Wikidata mediante consultas federadas.

## Requisitos Previos

Para ejecutar estas consultas, necesitarás:

1.  Un servidor de SPARQL (ej. Apache Jena Fuseki) en ejecución.
2.  El archivo `videogames_with_wikidata.ttl` cargado en el dataset.
3.  Conexión a internet para la consulta federada a Wikidata.


## Origen de datos

Los datos fueron sacados de Kaggle, este es el dataset usado: https://www.kaggle.com/datasets/sagayaabinesh/videogames

Para transformarlo usamos un mapeo simple de csv a rdf, dejandolo de la siguiente forma:

```
@prefix vg: <http://example.org/videogames/> .
@prefix vgo: <http://example.org/videogames/ontology/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

vg:wii-sports a vgo:VideoGame ;
    vgo:rank 1 ;
    vgo:name "Wii Sports" ;
    vgo:platform "Wii" ;
    vgo:year 2006 ;
    vgo:genre "Sports" ;
    vgo:publisher "Nintendo" ;
    vgo:naSales "41.49"^^xsd:decimal ;
    vgo:euSales "29.02"^^xsd:decimal ;
    vgo:jpSales "3.77"^^xsd:decimal ;
    vgo:otherSales "8.46"^^xsd:decimal ;
    vgo:globalSales "82.74"^^xsd:decimal .
    owl:sameAs <http://www.wikidata.org/entity/Q69503180> .

```

El atributo de sameAs no venia en el dataset y fue añadido despues de la conversion con otro script el cual buscaba el juego en wikidata y lo mapeaba, el resultado final dio alreadedor de 12400 con su entidad en wikidata, dejando 3500 que el script no encontro. (el script esta disponible en el repo)

## Prefijos Estándar

En las consultas se utilizan los siguientes prefijos:

```sparql
PREFIX vgo: <http://example.org/videogames/ontology/>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>
```

-----

## Consultas realizadas

### 1\. Top 10 Juegos en un plataforma y su Desarrolador (Q1)

**Objetivo:** Obtener el Top 10 de juegos por ventas globales del dataset local en una plataforma en especifico (usamos la PS2 en este caso) y buscar su desarollador (P178) en Wikidata.

```sql
PREFIX vgo: <http://example.org/videogames/ontology/>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?gameName ?globalSales ?developerLabel
WHERE {
  # --- Datos Locales ---
  {
    SELECT ?game ?gameName ?globalSales ?wikidataUri
    WHERE {
      ?game a vgo:VideoGame ;
            vgo:platform "PS2" ;
            vgo:name ?gameName ;
            vgo:globalSales ?globalSales ;
            owl:sameAs ?wikidataUri .
    }
    ORDER BY DESC(?globalSales)
    LIMIT 10
  }

  # --- Federación con Wikidata ---
  # Usa el ?wikidataUri para buscar el desarrollador (P178)
  SERVICE <https://query.wikidata.org/sparql> {
    ?wikidataUri wdt:P178 ?developer .
    ?developer rdfs:label ?developerLabel .
    FILTER(LANG(?developerLabel) = "en")
  }
}
```
-----

### 2\. Top juegos vendidos y su calficacion de edad (Q2)

**Objetivo:** Obtener el Top 10 de juegos por ventas globales del dataset local y buscar su calificacion de edad PEGI (P908) en Wikidata.

```sql
PREFIX vgo: <http://example.org/videogames/ontology/>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?gameName ?globalSales ?ratingLabel
WHERE {
  # --- Datos Locales ---
  {
    SELECT ?game ?gameName ?globalSales ?wikidataUri
    WHERE {
      ?game a vgo:VideoGame ;
            vgo:name ?gameName ;
            vgo:globalSales ?globalSales ;
            owl:sameAs ?wikidataUri . # Enlace a Wikidata
    }
    ORDER BY DESC(?globalSales)
    LIMIT 10
  }

  # --- Federación con Wikidata ---
  # Busca la calificación PEGI (P908)
  SERVICE <https://query.wikidata.org/sparql> {
    OPTIONAL {
      ?wikidataUri wdt:P908 ?rating .
      ?rating rdfs:label ?ratingLabel .
      FILTER(LANG(?ratingLabel) = "es" || LANG(?ratingLabel) = "en")
    }
  }
}
```

-----

### 3\. Top 200 juegos y sus pais de origen junto con su total de ventas (Q3)

**Objetivo:** Obtener el Top 200 de juegos por ventas globales del dataset local y agruparlos por pais gracias la propiedad (P495) en Wikidata, tambien sumar sus ventas.

```sql
PREFIX vgo: <http://example.org/videogames/ontology/>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?countryLabel 
       (COUNT(?name) AS ?numGames) 
       (SUM(?globalSales) AS ?totalSales)
WHERE {
    {
        SELECT ?name ?globalSales ?wikidataIRI
        WHERE {
            ?game a vgo:VideoGame ;
                vgo:name ?name ;
                vgo:globalSales ?globalSales ;
                owl:sameAs ?wikidataIRI .
        }
        ORDER BY DESC(?globalSales)
        LIMIT 200
    }
    # --- Federación con Wikidata ---
    # Busca el pais (P495)
    SERVICE <https://query.wikidata.org/sparql> {
        ?wikidataIRI wdt:P495 ?countryIRI .
        ?countryIRI rdfs:label ?countryLabel .
        FILTER(LANG(?countryLabel) = "es")
    }
}
GROUP BY ?countryLabel
ORDER BY DESC(?totalSales)
```

-----

### 4\. Top sagas por ventas (Q4)

**Objetivo:** Obtener el Top 1000 de juegos por ventas globales del dataset local, luego, usando Wikidata revisa una propiedad para ver si pertenence a una saga (P179), agrupandolas con sus ventas cumulativas y el pais en el que se desarollaron.

```sql
PREFIX vgo: <http://example.org/videogames/ontology/>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?sagaName ?countryName (SUM(?sales) AS ?totalSales)
WHERE {

  # --- Datos Locales ---
  {
    SELECT ?game ?sales ?wdGame
    WHERE {
      ?game a vgo:VideoGame ;
            vgo:globalSales ?sales ;
            owl:sameAs ?wdGame .
    }
    ORDER BY DESC(?sales)
    LIMIT 1000 #
  }

  # --- Federación con Wikidata ---
  # Busca la saga (P179)
  SERVICE <https://query.wikidata.org/sparql> {
    
    ?wdGame wdt:P179 ?wdSaga .
    
    ?wdSaga rdfs:label ?sagaName .
    FILTER(LANG(?sagaName) = "es" || LANG(?sagaName) = "en")
    
    OPTIONAL {
      ?wdSaga wdt:P495 ?country .
      ?country rdfs:label ?countryName .
      FILTER(LANG(?countryName) = "es" || LANG(?countryName) = "en")
    }
  }
}
# 3. Agregar por saga
GROUP BY ?sagaName ?countryName
ORDER BY DESC(?totalSales)
LIMIT 10
```

### 5\. Top 50 de ventas en un pais especifico (Q4)

**Objetivo:** Usando Wikidata, obtenemos juegos que fueron desarrollados (P945) en Suecia (Q34) y lo unimos con nuestro dataset para listar el top 50 de juegos mas vendidos que fueron desarrollados en suecia.

```sql
PREFIX vgo: <http://example.org/videogames/ontology/>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?gameName ?globalSales ?platform
WHERE {
  # --- Federación con Wikidata ---
  # Busca entidades de juegos cuyo pais de origen (P495) sea Suecia (Q34)
  SERVICE <https://query.wikidata.org/sparql> {
    ?wikidataUri wdt:P495 wd:Q34 .
  }

  # --- Datos Locales ---
  ?game a vgo:VideoGame ;
        vgo:name ?gameName ;
        vgo:globalSales ?globalSales ;
        vgo:platform ?platform ;
        owl:sameAs ?wikidataUri .
}
ORDER BY DESC(?globalSales)
LIMIT 50
```

