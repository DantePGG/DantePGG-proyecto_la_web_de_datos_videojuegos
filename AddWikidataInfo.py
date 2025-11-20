import requests
import time
import re
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, OWL, XSD
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import os

# Definir namespaces
VG = Namespace("http://example.org/videogames/")
VGO = Namespace("http://example.org/videogames/ontology/")

# Lock para escritura thread-safe
graph_lock = Lock()
stats_lock = Lock()

# Estadísticas en tiempo real
stats = {
    'processed': 0,
    'found': 0,
    'not_found': 0,
    'errors': 0
}

def search_wikidata(game_name, platform=None, year=None, use_auth=False, auth_token=None):
    """
    Busca un videojuego en Wikidata
    
    use_auth: Si es True, usa autenticación para mayor rate limit
    auth_token: Token de API de Wikidata (opcional pero recomendado)
    """
    clean_name = re.sub(r'\s*\([^)]*\)', '', game_name).strip()
    
    url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbsearchentities",
        "format": "json",
        "language": "en",
        "type": "item",
        "search": clean_name,
        "limit": 5
    }
    
    headers = {
        "User-Agent": "VideoGameLinker/2.0 (Educational Project; https://github.com/yourusername) Python/requests"
    }
    
    # Agregar token si está disponible
    if use_auth and auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("search"):
            return None
        
        for result in data["search"]:
            entity_id = result["id"]
            description = result.get("description", "").lower()
            
            if "video game" in description or "game" in description:
                # Verificación adicional por año si está disponible
                if year:
                    sparql_url = "https://query.wikidata.org/sparql"
                    sparql_query = f"""
                    SELECT ?year WHERE {{
                      wd:{entity_id} wdt:P577 ?publicationDate .
                      BIND(YEAR(?publicationDate) AS ?year)
                    }}
                    """
                    
                    try:
                        sparql_response = requests.get(
                            sparql_url,
                            params={"query": sparql_query, "format": "json"},
                            headers=headers,
                            timeout=15
                        )
                        sparql_data = sparql_response.json()
                        bindings = sparql_data.get("results", {}).get("bindings", [])
                        
                        if bindings:
                            wikidata_year = int(bindings[0]["year"]["value"])
                            if abs(wikidata_year - year) <= 1:
                                return f"http://www.wikidata.org/entity/{entity_id}"
                    except:
                        pass
                
                return f"http://www.wikidata.org/entity/{entity_id}"
        
        return None
        
    except Exception as e:
        return None

def process_game(game_info, use_auth=False, auth_token=None):
    """Procesa un juego individual"""
    game_uri, name, platform, year = game_info
    
    try:
        wikidata_uri = search_wikidata(name, platform, year, use_auth, auth_token)
        
        # Actualizar estadísticas
        with stats_lock:
            stats['processed'] += 1
            if wikidata_uri:
                stats['found'] += 1
            else:
                stats['not_found'] += 1
        
        # Sin autenticación: esperar más
        # Con autenticación: podemos ir más rápido
        sleep_time = 0.05 if use_auth else 0.1
        time.sleep(sleep_time)
        
        return (game_uri, name, wikidata_uri)
    except Exception as e:
        with stats_lock:
            stats['processed'] += 1
            stats['errors'] += 1
        return (game_uri, name, None)

# NUEVO: Se añade el parámetro 'not_found_file'
def process_ultra_fast(input_file, output_file, not_found_file, max_workers=5, limit=None, use_auth=False, auth_token=None):
    """
    Procesa el archivo TTL lo más rápido posible respetando los límites
    
    max_workers: Máximo 5 para SPARQL (límite de Wikidata)
    use_auth: Si True, usa autenticación (5000 req/hora vs 500 req/hora)
    auth_token: Tu token de API de Wikidata (obtenerlo en Special:BotPasswords)
    """
    print(f"📖 Leyendo archivo TTL...")
    
    g = Graph()
    g.parse(input_file, format="turtle")
    
    g.bind("vg", VG)
    g.bind("vgo", VGO)
    g.bind("owl", OWL)
    g.bind("xsd", XSD)
    
    # Recopilar juegos
    games_to_process = []
    total_games = 0
    already_has_uri = 0
    
    for game in g.subjects(RDF.type, VGO.VideoGame):
        total_games += 1
        
        if g.value(game, OWL.sameAs):
            already_has_uri += 1
            continue
        
        name = str(g.value(game, VGO.name))
        platform = str(g.value(game, VGO.platform)) if g.value(game, VGO.platform) else None
        year = int(g.value(game, VGO.year)) if g.value(game, VGO.year) else None
        sales = float(g.value(game, VGO.globalSales)) if g.value(game, VGO.globalSales) else 0
        
        games_to_process.append((game, name, platform, year, sales))
    
    # Ordenar por ventas
    games_to_process.sort(key=lambda x: x[4], reverse=True)
    
    if limit:
        games_to_process = games_to_process[:limit]
    
    # Calcular tiempo estimado
    if use_auth:
        rate = 83  # peticiones por minuto con auth
        workers_multiplier = min(max_workers, 5)
    else:
        rate = 8   # peticiones por minuto sin auth
        workers_multiplier = 1  # Sin auth, mejor ir despacio
    
    estimated_minutes = len(games_to_process) / (rate * workers_multiplier)
    
    print(f"\n{'='*60}")
    print(f"📊 CONFIGURACIÓN")
    print(f"{'='*60}")
    print(f"Total de juegos: {total_games}")
    print(f"Ya tienen URI: {already_has_uri}")
    print(f"A procesar: {len(games_to_process)}")
    print(f"Threads concurrentes: {max_workers}")
    print(f"Autenticación: {'✅ SÍ (5000/hora)' if use_auth else '❌ NO (500/hora)'}")
    print(f"Tiempo estimado: {estimated_minutes:.1f} minutos")
    print(f"{'='*60}\n")
    
    if not use_auth and len(games_to_process) > 500:
        print("⚠️  ADVERTENCIA: Sin autenticación, el límite es 500 req/hora")
        print("   Considera usar autenticación o reducir el límite a 400")
        print()
    
    # Procesar
    not_found = []
    start_time = time.time()
    last_update = start_time
    
    print("🔍 Procesando...\n")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        game_infos = [(g[0], g[1], g[2], g[3]) for g in games_to_process]
        
        future_to_game = {
            executor.submit(process_game, info, use_auth, auth_token): info 
            for info in game_infos
        }
        
        for future in as_completed(future_to_game):
            game_uri, name, wikidata_uri = future.result()
            
            if wikidata_uri:
                with graph_lock:
                    g.add((game_uri, OWL.sameAs, URIRef(wikidata_uri)))
            else:
                not_found.append(name)
            
            # Mostrar progreso cada segundo
            current_time = time.time()
            if current_time - last_update >= 1.0:
                elapsed = current_time - start_time
                progress = stats['processed'] / len(games_to_process) * 100
                rate_actual = stats['processed'] / (elapsed / 60) if elapsed > 0 else 0
                eta = (len(games_to_process) - stats['processed']) / rate_actual if rate_actual > 0 else 0
                
                print(f"\r[{stats['processed']}/{len(games_to_process)}] "
                      f"{progress:.1f}% | "
                      f"✅ {stats['found']} | "
                      f"❌ {stats['not_found']} | "
                      f"⏱️  {rate_actual:.1f} req/min | "
                      f"ETA: {eta:.1f} min", end='', flush=True)
                
                last_update = current_time
    
    print()  # Nueva línea después del progreso
    
    # Guardar
    print(f"\n💾 Guardando en: {output_file}")
    g.serialize(destination=output_file, format="turtle")
    
    # NUEVO: Guardar la lista de no encontrados en un archivo de texto
    if not_found:
        print(f"💾 Guardando {len(not_found)} nombres no encontrados en: {not_found_file}")
        try:
            # Usar un set para eliminar duplicados y luego ordenar
            unique_not_found = sorted(list(set(not_found)))
            with open(not_found_file, 'w', encoding='utf-8') as f:
                for name in unique_not_found:
                    f.write(f"{name}\n")
        except Exception as e:
            print(f"❌ Error al guardar {not_found_file}: {e}")

    # Estadísticas finales
    total_time = time.time() - start_time
    print(f"\n{'='*60}")
    print("📊 RESULTADOS FINALES")
    print(f"{'='*60}")
    print(f"Tiempo total: {total_time/60:.1f} minutos")
    print(f"Juegos procesados: {stats['processed']}")
    print(f"URIs encontrados: {stats['found']} ({stats['found']/stats['processed']*100:.1f}%)")
    print(f"No encontrados: {stats['not_found']}")
    print(f"Errores: {stats['errors']}")
    print(f"Velocidad promedio: {stats['processed']/(total_time/60):.1f} req/min")
    
    if not_found:
        print(f"\n⚠️  Primeros 30 no encontrados (de {len(not_found)} en total):")
        for name in not_found[:30]:
            print(f"  - {name}")
        if len(not_found) > 30:
            print(f"  ... y {len(not_found) - 30} más")
    
    print(f"\n✅ Proceso completado!")

# ==============================================================================
# MODO DE USO
# ==============================================================================

if __name__ == "__main__":
    # Si existe videogames_with_wikidata.ttl, lo usa como entrada (para agregar más URIs)
    # Si no existe, usa videogames.ttl (primera ejecución)
    
    import os
    
    original_file = "videogames.ttl"
    output_file = "videogames_with_wikidata.ttl"
    # NUEVO: Define el nombre del archivo de log para los no encontrados
    not_found_log_file = "not_found_games.txt"
    
    # Si el archivo de salida ya existe, usarlo como entrada
    if os.path.exists(output_file):
        input_file = output_file
        print(f"ℹ️  Usando archivo existente: {output_file}")
        print(f"   (Se agregarán más URIs a los que ya existen)\n")
    else:
        input_file = original_file
        print(f"ℹ️  Primera ejecución, usando: {original_file}\n")
    
    # OPCIÓN 1: Sin autenticación, top 200 por ejecución
    process_ultra_fast(input_file, output_file, not_found_log_file, max_workers=5, limit=7571, use_auth=False)
    
