import axios from 'axios';

const API_URL = 'http://104.208.67.128:8000';

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getStations = async () => {
  const response = await apiClient.get('/stations');
  return response.data;
};

export const getStationPrediction = async (id) => {
  const response = await apiClient.get(`/stations/${id}/prediction`);
  return response.data;
};

export const getStationHistory = async (id) => {
  const response = await apiClient.get(`/stations/${id}/history`);
  return response.data;
};

export const getStationForecast = async (id) => {
  const response = await apiClient.get(`/stations/${id}/forecast`);
  return response.data;
};

export const getAllStationStatus = async () => {
  const response = await apiClient.get('/stations/status/all');
  return response.data;
};

export const syncArcgisData = async () => {
  const response = await apiClient.post('/ingest/arcgis-sync');
  return response.data;
};

export const getStationAccuracy = async (id, hours = 48) => {
  const response = await apiClient.get(`/stations/${id}/accuracy?hours=${hours}`);
  return response.data;
};

export const getSystemLogs = async () => {
  const response = await apiClient.get('/system/logs');
  return response.data;
};
