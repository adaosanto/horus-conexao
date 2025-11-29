"""Router para visualização de gateways e tags em mapa"""
import json
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import GatewayModel, get_session_dependency

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def map_view(db: AsyncSession = Depends(get_session_dependency)):
    """Renderiza HTML com mapa mostrando gateways e tags"""
    
    # Busca todos os gateways
    result = await db.execute(select(GatewayModel))
    gateways = result.scalars().all()
    
    # Prepara os dados dos gateways para o JavaScript
    gateways_data = []
    for gw in gateways:
        geoloc = gw.geolocation
        if isinstance(geoloc, dict):            
            gateways_data.append({
                "name": gw.name,
                "mac": gw.mac,
                "lat": geoloc["latitude"],
                "lon": geoloc["longitude"]
            })
    
    # Gera o HTML com Leaflet
    html_content = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mapa de Gateways e Tags</title>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
        <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" />
        <style>
            body {{
                margin: 0;
                padding: 0;
                font-family: Arial, sans-serif;
            }}
            #map {{
                height: 100vh;
                width: 100%;
            }}
            .info-panel {{
                position: absolute;
                top: 10px;
                right: 10px;
                background: white;
                padding: 15px;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.3);
                z-index: 1000;
                max-width: 300px;
                max-height: 80vh;
                overflow-y: auto;
            }}
            .info-panel h2 {{
                margin-top: 0;
                font-size: 18px;
            }}
            .info-panel h3 {{
                font-size: 14px;
                margin: 10px 0 5px 0;
                color: #666;
            }}
            .gateway-item {{
                padding: 8px;
                margin: 5px 0;
                background: #f5f5f5;
                border-radius: 3px;
                border-left: 3px solid #007bff;
            }}
            .gateway-item strong {{
                color: #007bff;
            }}
            .tag-item {{
                padding: 6px;
                margin: 3px 0;
                background: #fff3cd;
                border-radius: 3px;
                border-left: 3px solid #ffc107;
                font-size: 12px;
            }}
            .tag-item strong {{
                color: #856404;
            }}
            .loading {{
                text-align: center;
                padding: 10px;
                color: #666;
            }}
            /* Efeito de pulso para gateways (radiofrequência) */
            @keyframes pulse {{
                0% {{
                    transform: scale(1);
                    opacity: 1;
                }}
                50% {{
                    transform: scale(1.5);
                    opacity: 0.5;
                }}
                100% {{
                    transform: scale(2);
                    opacity: 0;
                }}
            }}
            .gateway-pulse {{
                position: absolute;
                border-radius: 50%;
                background-color: #007bff;
                animation: pulse 2s infinite;
                pointer-events: none;
            }}
            .gateway-marker-container {{
                position: relative;
            }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <div class="info-panel">
            <h2>Dispositivos</h2>
            <h3>Gateways ({len(gateways_data)})</h3>
            <div id="gateways-list">
                {"".join([f'<div class="gateway-item"><strong>{gw["name"]}</strong><br><small>MAC: {gw["mac"]}</small></div>' for gw in gateways_data])}
            </div>
            <h3>Tags</h3>
            <div id="tags-list" class="loading">Carregando tags...</div>
        </div>
        
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
        <script>
            // Dados dos gateways
            const gateways = {json.dumps(gateways_data)};
            
            // Inicializa o mapa
            let map;
            if (gateways.length > 0) {{
                // Calcula o centro baseado nos gateways
                const avgLat = gateways.reduce((sum, gw) => sum + gw.lat, 0) / gateways.length;
                const avgLon = gateways.reduce((sum, gw) => sum + gw.lon, 0) / gateways.length;
                
                map = L.map('map').setView([avgLat, avgLon], 13);
            }} else {{
                // Se não houver gateways, usa uma localização padrão (Brasil)
                map = L.map('map').setView([-14.2350, -51.9253], 4);
            }}
            
            // Adiciona tile layer do OpenStreetMap
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '© OpenStreetMap contributors',
                maxZoom: 19
            }}).addTo(map);
            
            // Cria grupos de marcadores para clustering
            const gatewayMarkers = L.markerClusterGroup();
            const tagMarkers = L.markerClusterGroup();
            
            // Ícone personalizado para gateways (azul) com efeito de pulso
            const gatewayIcon = L.divIcon({{
                className: 'gateway-marker-container',
                html: `
                    <div class="gateway-pulse" style="width: 20px; height: 20px; left: 0; top: 0;"></div>
                    <div class="gateway-pulse" style="width: 20px; height: 20px; left: 0; top: 0; animation-delay: 0.5s;"></div>
                    <div class="gateway-pulse" style="width: 20px; height: 20px; left: 0; top: 0; animation-delay: 1s;"></div>
                    <div style="position: relative; background-color: #007bff; width: 20px; height: 20px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3); z-index: 10;"></div>
                `,
                iconSize: [20, 20],
                iconAnchor: [10, 10]
            }});
            
            // Ícone personalizado para tags (amarelo/laranja)
            const tagIcon = L.divIcon({{
                className: 'tag-marker',
                html: '<div style="background-color: #ffc107; width: 15px; height: 15px; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>',
                iconSize: [15, 15],
                iconAnchor: [7, 7]
            }});
            
            // Adiciona marcadores para cada gateway
            gateways.forEach(gw => {{
                const marker = L.marker([gw.lat, gw.lon], {{ icon: gatewayIcon }});
                marker.bindPopup(`
                    <b>${{gw.name}}</b><br>
                    <strong>Gateway</strong><br>
                    MAC: ${{gw.mac}}<br>
                    Coordenadas: ${{gw.lat.toFixed(6)}}, ${{gw.lon.toFixed(6)}}
                `);
                gatewayMarkers.addLayer(marker);
            }});
            
            map.addLayer(gatewayMarkers);
            map.addLayer(tagMarkers);
            
            // Busca dados das tags do endpoint /stats
            async function loadTags() {{
                try {{
                    const response = await fetch('/stats');
                    const tags = await response.json();
                    
                    // Salva informações sobre popups abertos antes de limpar
                    let openPopupInfo = null;
                    tagMarkers.eachLayer(function(marker) {{
                        if (marker.isPopupOpen()) {{
                            // Salva o MAC da tag que tinha popup aberto
                            const popupContent = marker.getPopup().getContent();
                            const macMatch = popupContent.match(/<b>([^<]+)<\/b>/);
                            if (macMatch) {{
                                openPopupInfo = {{
                                    mac: macMatch[1],
                                    lat: marker.getLatLng().lat,
                                    lon: marker.getLatLng().lng
                                }};
                            }}
                        }}
                    }});
                    
                    // Limpa marcadores de tags existentes antes de adicionar novos
                    tagMarkers.clearLayers();
                    
                    // Atualiza lista de tags no painel
                    const tagsList = document.getElementById('tags-list');
                    if (tags.length === 0) {{
                        tagsList.innerHTML = '<div class="loading">Nenhuma tag encontrada</div>';
                    }} else {{
                        tagsList.innerHTML = tags.map(tag => `
                            <div class="tag-item">
                                <strong>${{tag.mac}}</strong><br>
                                <small>RSSI: ${{tag.last_rssi}} | ${{tag.presence}}</small>
                            </div>
                        `).join('');
                    }}
                    
                    // Adiciona marcadores para tags com coordenadas
                    const tagsWithCoords = tags.filter(tag => tag.latitude && tag.longitude);
                    let markerToReopen = null;
                    
                    tagsWithCoords.forEach(tag => {{
                        const marker = L.marker([tag.latitude, tag.longitude], {{ icon: tagIcon }});
                        const presenceColor = tag.presence === 'present' ? '#28a745' : '#dc3545';
                        marker.bindPopup(`
                            <b>${{tag.mac}}</b><br>
                            <strong>Tag BLE</strong><br>
                            RSSI: ${{tag.last_rssi}} dBm<br>
                            Gateway: ${{tag.gateway}}<br>
                            Status: <span style="color: ${{presenceColor}}">${{tag.presence}}</span><br>
                            Última vez: ${{tag.last_seen_humanized}}<br>
                            Coordenadas: ${{tag.latitude.toFixed(6)}}, ${{tag.longitude.toFixed(6)}}
                        `);
                        tagMarkers.addLayer(marker);
                        
                        // Se este marcador corresponde ao que tinha popup aberto, marca para reabrir
                        if (openPopupInfo && tag.mac === openPopupInfo.mac) {{
                            markerToReopen = marker;
                        }}
                    }});
                    
                    // Reabre o popup se estava aberto antes
                    if (markerToReopen) {{
                        setTimeout(() => {{
                            markerToReopen.openPopup();
                        }}, 100);
                    }}
                    
                    // Ajusta o zoom para mostrar todos os dispositivos (apenas na primeira carga)
                    if (gateways.length > 0 || tagsWithCoords.length > 0) {{
                        const allMarkers = [];
                        gateways.forEach(gw => allMarkers.push(L.marker([gw.lat, gw.lon])));
                        tagsWithCoords.forEach(tag => allMarkers.push(L.marker([tag.latitude, tag.longitude])));
                        const group = new L.featureGroup(allMarkers);
                        // Só ajusta zoom se o mapa ainda não foi ajustado
                        if (!map._initialBoundsSet) {{
                            map.fitBounds(group.getBounds().pad(0.1));
                            map._initialBoundsSet = true;
                        }}
                    }}
                }} catch (error) {{
                    console.error('Erro ao carregar tags:', error);
                    document.getElementById('tags-list').innerHTML = '<div class="loading" style="color: red;">Erro ao carregar tags</div>';
                }}
            }}
            
            // Carrega tags ao inicializar
            loadTags();
            
            // Atualiza tags a cada 10 segundos
            setInterval(loadTags, 10000);
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)

