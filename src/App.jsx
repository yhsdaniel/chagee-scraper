import { useState, useEffect } from 'react';

const FALLBACK_URL = "https://github.com/yhsdaniel/chagee-scraper/releases/download/v1.0.5/CHAGEE-Scraper-Setup-1.0.5.exe";

export default function App() {
  const [folder, setFolder] = useState('');
  const [logs, setLogs] = useState('');
  const [running, setRunning] = useState(null);

  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  const refreshLogin = async () => {
    const ok = await window.electron.checkLogin();
    setIsLoggedIn(ok);
  };

  useEffect(() => { refreshLogin(); }, []);

  const [release, setRelease] = useState(null)
  useEffect(() => {
    fetch(`https://api.github.com/repos/yhsdaniel/chagee-scraper/releases/latest`)
      .then(r => {
        if (!r.ok) throw new Error(`Github ${r.status}`)
        return r.json()
      })
      .then(setRelease)
      .catch(err => {
        console.log('Github API gagal, pakai fallback: ', err.message)
      })
  }, [])
  // FILTER: hanya .exe yang BUKAN blockmap
  const exe = release?.assets?.filter(r => r.name.includes(".exe") && !r.name.includes(".blockmap"))[0]
  const downloadUrl = exe?.browser_download_url || FALLBACK_URL

  useEffect(() => {
    window.electronAPI?.onLog?.((data) => {
      setLogs(prev => prev + data + '\n');
    });
  }, []);

  useEffect(() => {
    window.electron?.onUpdateAvailable?.((version) => {
      alert(`Update ${version} lagi download...`);
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
      {exe ?
        <a
          href={downloadUrl}
          download
          style={{ display: 'inline-block', background: '#000', color: '#fff', padding: '16px 32px', borderRadius: 12, textDecoration: 'none', fontWeight: 'bold', marginTop: 20 }}
        >
          Download untuk PC - {release?.tag_name}
        </a>
        :
        <a
          style={{ display: 'inline-block', background: '#000', color: '#fff', padding: '16px 32px', borderRadius: 12, textDecoration: 'none', fontWeight: 'bold', marginTop: 20 }}
        >
          Downloading...
        </a>
      }

      <h1>Chagee Scraping Dashboard</h1>

      <div className="mt-4 p-4 border rounded">
        <p>Status: {isLoggedIn ? '✅ Sudah Login (shared)' : '❌ Belum Login'}</p>
        <p className="text-sm text-gray-500">Session di: python/shared/storage_state.json</p>

        {!isLoggingIn ? (
          <button onClick={async () => { setIsLoggingIn(true); await window.electron.startLogin(); }} className="bg-blue-600 text-white px-4 py-2 rounded mt-2">
            Buka Browser Login
          </button>
        ) : (
          <div className="mt-2">
            <p>Login di browser yang terbuka, kalau sudah masuk dashboard klik:</p>
            <button onClick={async () => { await window.electron.saveSession(); setIsLoggingIn(false); setTimeout(refreshLogin, 500); }} className="bg-green-600 text-white px-4 py-2 rounded mt-2">
              Simpan Session ke Shared
            </button>
          </div>
        )}
      </div>

      <div className="mt-4 flex gap-2">
        <button disabled={!isLoggedIn} onClick={() => window.electron.runWow()} className="bg-black text-white px-4 py-2 rounded disabled:opacity-40">
          Jalankan WOW-to-GS
        </button>
        <button disabled={!isLoggedIn} onClick={() => window.electron.runProducts()} className="bg-black text-white px-4 py-2 rounded disabled:opacity-40">
          Jalankan Products
        </button>
      </div>

      <p className="text-xs text-gray-400 mt-2">2 scraper ini pakai session yang sama, jadi login 1x saja cukup.</p>

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