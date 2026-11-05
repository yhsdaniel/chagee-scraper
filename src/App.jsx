import { useState, useEffect } from 'react';

export default function App() {
  const [folder, setFolder] = useState('');
  const [logs, setLogs] = useState('');
  const [running, setRunning] = useState(null);

  const [version, setVersion] = useState("v1.0.3")
  const [downloading, setDownloading] = useState(false)
  useEffect(() => {
    fetch(`https://api.github.com/repos/chagee-scraper/releases/latest`)
      .then(r => r.json())
      .then(d => {
        if (d.tag_name) setVersion(d.tag_name)
      })
      .catch(() => { })
  }, [])
  const directDownload = `https://github.com/yhsdaniel/chagee-scraper/releases/latest/download/CHAGEE-Scraper-Setup-${version.replace('v', '')}.exe`
  const fallbackDownload = `https://github.com/yhsdaniel/chagee-scraper/releases/latest`

  const handleDownload = () => {
    setDownloading(true)
    window.location.href = directDownload
    // Kalau 3 detik tidak download, redirect ke releases page
    setTimeout(() => {
      fetch(directDownload, { method: 'HEAD' })
        .then(r => {
          if (!r.ok) window.location.href = fallbackDownload
        })
        .catch(() => window.location.href = fallbackDownload)
        .finally(() => setDownloading(false))
    }, 3000)
  }

  useEffect(() => {
    window.electronAPI?.onLog?.((data) => {
      setLogs(prev => prev + data + '\n');
    });
  }, []);

  const pickFolder = async () => {
    if (!window.electronAPI?.selectFolder) return alert('Electron API is not available');
    const f = await window.electronAPI.selectFolder();
    if (f) setFolder(f);
  }

  const run = async (project) => {
    if (!folder) return alert('Select local folder first!');
    if (!window.electronAPI?.runProject) return alert('Electron API is not available');
    setRunning(project);
    setLogs(`Starting ${project} with folder: ${folder}\n`);
    await window.electronAPI.runProject(project, folder);
    setRunning(null);
  }

  return (
    <div style={{ padding: 20, fontFamily: 'sans-serif' }}>
      <div style={{ background: '#000', color: '#fff', padding: 20, borderRadius: 16, marginTop: 30 }}>
        <p>Latest Version: {version}</p>
        <button
          onClick={handleDownload}
          style={{ background: '#fff', color: '#000', padding: '14px 28px', borderRadius: 10, fontWeight: 'bold', border: 'none', cursor: 'pointer', marginTop: 10 }}
        >
          {downloading ? 'Downloading...' : '⬇️ Download for 【entity-Windows¦canonical_name=Windows】'}
        </button>
        <p style={{ fontSize: 12, marginTop: 10, opacity: 0.7 }}>
          If download doesn't start, <a href={fallbackDownload} style={{ color: '#fff' }}>click here</a>
        </p>
      </div>

      <h1>Chagee Scraping Dashboard</h1>

      <div style={{ border: '1px solid #ddd', padding: 15, borderRadius: 8 }}>
        <p>Local Folder: <b>{folder || 'Not selected'}</b></p>
        <button onClick={pickFolder}>Select Local Folder</button>
      </div>

      <div style={{ display: 'flex', gap: 15, marginTop: 20 }}>
        <button onClick={() => run('Login')} disabled={running} style={{ padding: '20px', flex: 1 }}>
          {running === 'Login' ? 'Running...' : 'Login'}
        </button>
      </div>

      <div style={{ display: 'flex', gap: 15, marginTop: 20 }}>
        <button onClick={() => run('MTD')} disabled={running} style={{ padding: '20px', flex: 1 }}>
          {running === 'MTD' ? 'Running...' : 'MTD to Gsheets'}
        </button>
        <button onClick={() => run('Download store')} disabled={running} style={{ padding: '20px', flex: 1 }}>
          {running === 'Download store' ? 'Running...' : 'Download Store'}
        </button>
      </div>

      <div style={{ display: 'flex', gap: 15, marginTop: 20 }}>
        <button onClick={() => run('WOW')} disabled={running} style={{ padding: '20px', flex: 1 }}>
          {running === 'WOW' ? 'Running...' : 'WOW to Gsheets'}
        </button>
        <button onClick={() => run('Products')} disabled={running} style={{ padding: '20px', flex: 1 }}>
          {running === 'Products' ? 'Running...' : 'Products to Gsheets'}
        </button>
      </div>

      <pre style={{ background: '#111', color: '#0f0', padding: 15, height: 400, overflow: 'auto', marginTop: 20, textAlign: 'left' }}>
        {logs}
      </pre>
    </div>
  )
}