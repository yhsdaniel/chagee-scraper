import { useState, useEffect } from 'react';

export default function App() {
  const [folder, setFolder] = useState('');
  const [logs, setLogs] = useState('');
  const [running, setRunning] = useState(null);

  const [release, setRelease] = useState < any > (null)
  useEffect(() => {
    fetch(`https://api.github.com/repos/yhsdaniel/chagee-scraper/releases/latest`)
      .then(r => r.json())
      .then(setRelease)
  }, [])
  const exe = release?.assets?.find((a) => a.name.endsWith('.exe'))

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
      <a
        href={`https://api.github.com/repos/yhsdaniel/chagee-scraper/releases/latest`}
        style={{ display: 'inline-block', background: '#000', color: '#fff', padding: '16px 32px', borderRadius: 12, textDecoration: 'none', fontWeight: 'bold', marginTop: 20 }}
      >
        Download latest version
      </a>

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