// PROJECT CREATIVE LAYER (free zone for the third model's own creative touches - see 07 and 03).
// ExtrasMap renders above the map stage (under cards); ExtrasTop renders above everything except the audio.
// Use cameraAt(t) + project(cam, ...px(lon, lat)) to attach elements to the map. Must pass the quality gate (06).
import React from 'react';
export const ExtrasMap: React.FC<{t: number}> = () => null;
export const ExtrasTop: React.FC<{t: number}> = () => null;
