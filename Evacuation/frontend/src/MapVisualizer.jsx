import React from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

import L from 'leaflet';
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
    iconUrl: icon,
    shadowUrl: iconShadow,
    iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

const MapVisualizer = ({ incidentData }) => {
    const defaultCenter = [34.0522, -118.2437];
    const center = incidentData?.target_zone?.centroid || defaultCenter;

    return (
        <div style={{ position: 'relative', width: '100%', height: '100%' }}>
            <MapContainer 
                center={center} 
                zoom={12} 
                style={{ height: '100%', width: '100%', borderRadius: '20px', boxShadow: '0 10px 25px -5px rgba(0,0,0,0.1)' }}
            >
                <TileLayer
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    attribution='&copy; OpenStreetMap contributors'
                />
                {incidentData && (
                    <Marker position={incidentData.target_zone.centroid}>
                        <Popup>
                            <b>{incidentData.target_zone.settlement_name}</b><br/>
                            Pop: {incidentData.target_zone.estimated_population}
                        </Popup>
                    </Marker>
                )}
                {incidentData?.routing_solution?.designated_safe_zones?.map((zone) => (
                    <Marker key={zone.id} position={zone.coords}>
                        <Popup>Safe Zone: {zone.name}</Popup>
                    </Marker>
                ))}
            </MapContainer>

            {/* FLOATING LEGEND OVERLAY */}
            <div style={{
                position: 'absolute',
                bottom: '24px',
                right: '24px',
                background: 'rgba(255, 255, 255, 0.95)',
                backdropFilter: 'blur(10px)',
                padding: '20px',
                borderRadius: '16px',
                boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)',
                zIndex: 1000, /* Above map tiles */
                width: '200px'
            }}>
                <h4 style={{ margin: '0 0 16px 0', fontSize: '14px', color: '#0f172a' }}>Map Legend</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px', color: '#334155', fontWeight: '500' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><span>🔥</span> Fire Origin</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><span>⚠️</span> Predicted Spread</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><span>🟢</span> Safe Zone</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><span>🚧</span> Evacuation Route</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><span>🏥</span> Hospitals</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><span>🚒</span> Fire Units</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><span>🚑</span> Ambulances</div>
                </div>
            </div>
        </div>
    );
};

export default MapVisualizer;
