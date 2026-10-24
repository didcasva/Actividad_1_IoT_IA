const $ = id => document.getElementById(id);
let devices = [], charts = [], busy = false;
const timestamp = s => new Date(/Z$|[+-]\d\d:\d\d$/.test(s) ? s : s + 'Z');
const date = s => timestamp(s).toLocaleString('es-CO');

function params() {
  const p = new URLSearchParams();
  if ($('device').value) p.set('device_id', $('device').value);
  for (const key of ['start', 'end']) {
    if ($(key).value) p.set(key, new Date($(key).value).toISOString());
  }
  return p;
}

async function json(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

for (const id of ['maxTemp', 'maxHumidity']) {
  $(id).value = localStorage.getItem(id) || $(id).value;
  $(id).onchange = () => {
    localStorage.setItem(id, $(id).value);
    refresh();
  };
}

function renderReception(current) {
  $('liveStatus').className = 'warn';
  if (!current) {
    $('liveStatus').textContent = 'Todavía no se han recibido mediciones de esta unidad.';
    return;
  }
  const age = Math.max(0, Math.floor((Date.now() - timestamp(current.received_at).getTime()) / 1000));
  if (age > 30) {
    $('liveStatus').textContent = `Sin recepción reciente · última recepción: ${date(current.received_at)}. Comprueba que el ESP32 esté encendido y conectado al Wi-Fi.`;
  } else {
    $('liveStatus').className = 'live';
    $('liveStatus').textContent = `Recibiendo mediciones · última recepción hace ${age} s.`;
  }
}

function renderCharts(rows) {
  if (typeof Chart === 'undefined') {
    $('status').textContent += ' · Gráficas no disponibles: revise el archivo Chart.js local';
    return;
  }
  for (const chart of charts) chart.destroy();
  const chronological = [...rows].reverse();
  charts = [
    ['temperatureChart', 'temperature_c', '#17766b'],
    ['humidityChart', 'humidity_percent', '#377cb5']
  ].map(([id, key, color]) => new Chart($(id), {
    type: 'line',
    data: {
      labels: chronological.map(r => date(r.measured_at)),
      datasets: devices.filter(d => chronological.some(r => r.device_id === d.id)).map((d, i) => ({
        label: `${d.name} · ${d.device_code}`,
        data: chronological.map(r => r.device_id === d.id ? r[key] : null),
        borderColor: i ? `hsl(${i * 87 % 360},55%,42%)` : color,
        spanGaps: true, tension: .2, pointRadius: 2
      }))
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      scales: {x: {ticks: {maxTicksLimit: 6}}}
    }
  }));
}

async function refresh() {
  if (busy) return;
  busy = true;
  try {
    const p = params();
    $('export').href = '/api/v1/readings/export.csv?' + p;
    const currentFilter = new URLSearchParams();
    if ($('device').value) currentFilter.set('device_id', $('device').value);
    const [rows, last, current] = await Promise.all([
      json('/api/v1/readings?limit=200&' + p),
      json('/api/v1/readings/latest?' + p),
      json('/api/v1/readings/latest?' + currentFilter)
    ]);
    $('status').className = '';
    $('status').textContent = last ? 'Consulta actualizada' : 'Sin datos en el período seleccionado';
    $('temp').textContent = last ? last.temperature_c.toFixed(1) : '—';
    $('humidity').textContent = last ? last.humidity_percent.toFixed(1) : '—';
    $('time').textContent = last ? date(last.measured_at) : '—';
    const device = last && devices.find(d => d.id === last.device_id);
    $('unit').textContent = device ? `${device.name} · ${device.device_code} · ${device.sensor_type}` : '—';
    renderReception(current);
    if (last && (last.temperature_c > Number($('maxTemp').value) ||
                 last.humidity_percent > Number($('maxHumidity').value))) {
      $('status').textContent += ' · Umbral superado';
      $('status').className = 'warn';
    }
    $('rows').replaceChildren();
    for (const row of rows) {
      const tr = document.createElement('tr');
      const unit = devices.find(d => d.id === row.device_id);
      for (const value of [date(row.measured_at), unit ? `${unit.name} · ${unit.device_code}` : row.device_id,
        row.temperature_c.toFixed(1) + ' °C', row.humidity_percent.toFixed(1) + ' %']) {
        const td = document.createElement('td');
        td.textContent = value;
        tr.append(td);
      }
      $('rows').append(tr);
    }
    renderCharts(rows);
  } catch (error) {
    $('status').textContent = 'Error al consultar: ' + error.message;
    $('status').className = 'error';
    $('liveStatus').textContent = 'No se puede comprobar la recepción. Los valores visibles corresponden a la última consulta correcta.';
    $('liveStatus').className = 'warn';
  } finally {
    busy = false;
  }
}

async function init() {
  try {
    devices = await json('/api/v1/devices');
    for (const device of devices) {
      const option = document.createElement('option');
      option.value = device.id;
      option.textContent = `${device.name} · ${device.device_code} · ${device.location}`;
      $('device').append(option);
    }
    const query = new URLSearchParams(location.search);
    const code = query.get('device_code');
    const id = query.get('device_id');
    if (code || id) {
      const chosen = devices.find(d => code ? d.device_code === code : String(d.id) === id);
      if (!chosen) throw new Error('La unidad solicitada no está registrada');
      $('device').value = chosen.id;
    } else if (query.get('all') !== '1') {
      // Al abrir, elegir la unidad de la medición más reciente. Los datos de
      // prueba anteriores permanecen accesibles mediante el selector.
      const latest = await json('/api/v1/readings/latest');
      const chosen = devices.find(d => d.id === latest?.device_id) || devices.find(d => d.is_active);
      if (chosen) $('device').value = chosen.id;
    }
    await refresh();
    setInterval(refresh, 5000);
  } catch (error) {
    $('status').textContent = 'No se pudieron cargar las unidades: ' + error.message;
    $('status').className = 'error';
  }
}

$('apply').onclick = refresh;
$('device').onchange = () => {
  const url = new URL(location.href);
  url.searchParams.delete('device_id');
  url.searchParams.delete('device_code');
  url.searchParams.delete('all');
  const chosen = devices.find(d => String(d.id) === $('device').value);
  if (chosen) url.searchParams.set('device_code', chosen.device_code);
  else url.searchParams.set('all', '1');
  history.replaceState(null, '', url);
  refresh();
};
init();
