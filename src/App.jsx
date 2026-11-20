import { useState, useEffect, useRef } from 'react';

const REPO_OWNER = "yhsdaniel";
const REPO_NAME = "chagee-scraper";
const FALLBACK_DOWNLOAD_URL = `https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/latest`;

export default function App() {
  const isElectron = typeof window !== 'undefined' && Boolean(window.electron || window.electronAPI);

  // State untuk Desktop Electron
  const [appVersion, setAppVersion] = useState('1.0.5');
  const [userDataInfo, setUserDataInfo] = useState({ userData: '', storagePath: '' });
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [folder, setFolder] = useState('');
  const [logs, setLogs] = useState('');
  const [runningJob, setRunningJob] = useState(null);
  const [saveTriggerStatus, setSaveTriggerStatus] = useState('');

  // State untuk Auto-Update (Desktop)
  const [updateInfo, setUpdateInfo] = useState({
    status: 'idle', // 'idle' | 'checking' | 'available' | 'downloading' | 'ready' | 'error'
    version: null,
    percent: 0,
    message: ''
  });

  // State untuk Web (Vercel Download Page)
  const [latestRelease, setLatestRelease] = useState(null);
  const [fetchingRelease, setFetchingRelease] = useState(true);

  const logContainerRef = useRef(null);

  // Auto-scroll logs
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  // Fetch info rilis GitHub (berfungsi di Web Vercel & fallback)
  useEffect(() => {
    fetch(`https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest`)
      .then((res) => {
        if (!res.ok) throw new Error(`GitHub API Status: ${res.status}`);
        return res.json();
      })
      .then((data) => {
        setLatestRelease(data);
        setFetchingRelease(false);
      })
      .catch((err) => {
        console.warn('Gagal memuat rilis GitHub terbaru:', err.message);
        setFetchingRelease(false);
      });
  }, []);

  // Filter asset file installer .exe (bukan .blockmap atau checksum)
  const exeAsset = latestRelease?.assets?.find(
    (a) => a.name.toLowerCase().endsWith('.exe') && !a.name.toLowerCase().endsWith('.blockmap')
  );
  const directDownloadUrl = exeAsset?.browser_download_url || FALLBACK_DOWNLOAD_URL;
  const releaseVersion = latestRelease?.tag_name || `v${appVersion}`;
  const fileSizeMb = exeAsset?.size ? (exeAsset.size / (1024 * 1024)).toFixed(1) : null;

  // Inisialisasi Electron Desktop
  useEffect(() => {
    const api = window.electron || window.electronAPI;
    if (!api) return;

    // Ambil versi aplikasi
    api.getVersion?.()
      .then((ver) => ver && setAppVersion(ver))
      .catch(() => {});

    // Ambil path session
    api.getUserDataPath?.()
      .then((info) => info && setUserDataInfo(info))
      .catch(() => {});

    // Periksa status login
    api.checkLogin?.()
      .then((loggedIn) => setIsLoggedIn(Boolean(loggedIn)))
      .catch(() => {});

    // Listener logs streaming dari Python process
    const cleanupLog = api.onLog?.((data) => {
      setLogs((prev) => prev + data + '\n');
    });

    // Listener auto-updater
    const cleanupUpdateAvailable = api.onUpdateAvailable?.((version) => {
      setUpdateInfo({
        status: 'available',
        version: version,
        percent: 0,
        message: `Update v${version} ditemukan, sedang mendownload...`
      });
    });

    const cleanupUpdateProgress = api.onUpdateProgress?.((percent) => {
      setUpdateInfo((prev) => ({
        ...prev,
        status: 'downloading',
        percent: percent,
        message: `Mengunduh update: ${percent}%`
      }));
    });

    const cleanupUpdateDownloaded = api.onUpdateDownloaded?.((info) => {
      const ver = typeof info === 'string' ? info : info?.version;
      setUpdateInfo({
        status: 'ready',
        version: ver,
        percent: 100,
        message: `Update v${ver || ''} siap diinstall!`
      });
    });

    return () => {
      if (typeof cleanupLog === 'function') cleanupLog();
      if (typeof cleanupUpdateAvailable === 'function') cleanupUpdateAvailable();
      if (typeof cleanupUpdateProgress === 'function') cleanupUpdateProgress();
      if (typeof cleanupUpdateDownloaded === 'function') cleanupUpdateDownloaded();
    };
  }, [isElectron]);

  const handleSelectFolder = async () => {
    const api = window.electron || window.electronAPI;
    if (!api?.selectFolder) return;
    try {
      const selected = await api.selectFolder();
      if (selected) {
        setFolder(selected);
        setLogs((prev) => prev + `[INFO] Folder kerja dipilih: ${selected}\n`);
      }
    } catch (err) {
      alert(`Gagal memilih folder: ${err.message}`);
    }
  };

  const handleRun = async (projectName) => {
    const api = window.electron || window.electronAPI;
    if (!api?.runProject) {
      alert('Fitur ini hanya dapat dijalankan di Aplikasi Desktop Windows!');
      return;
    }

    if (projectName === 'Download store' || projectName === 'Products') {
      if (!folder) {
        alert('Silakan pilih Folder Kerja terlebih dahulu untuk menyimpan/membaca data toko!');
        return;
      }
    }

    setRunningJob(projectName);
    setSaveTriggerStatus('');
    setLogs((prev) => prev + `\n--- [${projectName}] Menjalankan job: ${projectName} ---\n`);

    try {
      const res = await api.runProject(projectName, folder);
      if (res?.status === 'error') {
        alert(res?.message || 'Gagal memulai proses');
        setRunningJob(null);
      }
    } catch (err) {
      setLogs((prev) => prev + `[SYSTEM ERROR] ${err.message}\n`);
      setRunningJob(null);
    }
  };

  const handleSaveSession = async () => {
    const api = window.electron || window.electronAPI;
    if (!api?.saveSession) return;
    setSaveTriggerStatus('Mengirim sinyal simpan session...');
    try {
      const ok = await api.saveSession();
      if (ok) {
        setSaveTriggerStatus('✅ Sinyal simpan terkirim! Browser akan menyimpan token.');
        // Tunggu sebentar lalu refresh status login
        setTimeout(async () => {
          const logged = await api.checkLogin?.();
          setIsLoggedIn(Boolean(logged));
        }, 3000);
      } else {
        setSaveTriggerStatus('❌ Gagal mengirim sinyal simpan.');
      }
    } catch (err) {
      setSaveTriggerStatus(`❌ Error: ${err.message}`);
    }
  };

  const handleRefreshLogin = async () => {
    const api = window.electron || window.electronAPI;
    if (!api?.checkLogin) return;
    const logged = await api.checkLogin();
    setIsLoggedIn(Boolean(logged));
  };

  const handleLogout = async () => {
    const api = window.electron || window.electronAPI;
    if (!api?.logout) return;
    if (!confirm('Yakin ingin logout dan menghapus shared session di komputer ini?')) return;
    await api.logout();
    setIsLoggedIn(false);
    setLogs((prev) => prev + `[INFO] Shared session berhasil dihapus.\n`);
  };

  const handleApplyUpdate = async () => {
    const api = window.electron || window.electronAPI;
    if (api?.quitAndInstall) {
      await api.quitAndInstall();
    }
  };

  // ==========================================
  // VIEW: LANDING PAGE WEB (DI DEPLOY KE VERCEL)
  // ==========================================
  if (!isElectron) {
    return (
      <div style={{ minHeight: '100vh', backgroundColor: '#0f172a', color: '#f8fafc', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
        {/* Navbar */}
        <header style={{ borderBottom: '1px solid #1e293b', padding: '16px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 24 }}>🍃</span>
            <span style={{ fontSize: 18, fontWeight: 700, letterSpacing: '0.5px' }}>CHAGEE Scraper Portal</span>
          </div>
          <div>
            <span style={{ backgroundColor: '#1e293b', padding: '6px 14px', borderRadius: 20, fontSize: 13, color: '#94a3b8' }}>
              Versi Rilis: <b>{releaseVersion}</b>
            </span>
          </div>
        </header>

        {/* Hero Section */}
        <main style={{ maxWidth: 900, margin: '0 auto', padding: '60px 20px', textAlign: 'center' }}>
          <div style={{ display: 'inline-block', backgroundColor: '#1e3a8a', color: '#60a5fa', padding: '6px 16px', borderRadius: 9999, fontSize: 13, fontWeight: 600, marginBottom: 20 }}>
            Automasi Scraping CHAGEE Dashboard ke Google Sheets
          </div>

          <h1 style={{ fontSize: 44, fontWeight: 800, margin: '16px 0', lineHeight: 1.2 }}>
            Aplikasi Desktop Scraper CHAGEE
          </h1>

          <p style={{ fontSize: 18, color: '#94a3b8', maxWidth: 680, margin: '0 auto 36px', lineHeight: 1.6 }}>
            Jalankan 5 scraper sekaligus: <b>Login 1x Shared</b>, <b>MTD</b>, <b>WOW</b>, <b>Products</b>, dan <b>Download Store</b> tanpa perlu install Python, venv, atau terminal.
          </p>

          {/* Tombol Download Utama */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
            <a
              href={directDownloadUrl}
              download
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 12,
                backgroundColor: '#2563eb',
                color: '#ffffff',
                padding: '18px 36px',
                borderRadius: 14,
                textDecoration: 'none',
                fontWeight: 700,
                fontSize: 18,
                boxShadow: '0 10px 25px -5px rgba(37, 99, 235, 0.4)',
                transition: 'all 0.2s ease',
                cursor: 'pointer'
              }}
            >
              <span>📥</span>
              <span>{fetchingRelease ? 'Mempersiapkan Unduhan...' : `Download untuk Windows (.exe) - ${releaseVersion}`}</span>
            </a>

            <div style={{ fontSize: 13, color: '#64748b', display: 'flex', gap: 16 }}>
              <span>✓ Windows 10/11 64-bit</span>
              {fileSizeMb && <span>✓ Ukuran: ~{fileSizeMb} MB</span>}
              <span>✓ Termasuk Python & Chromium</span>
            </div>
          </div>

          {/* Panduan Cepat 4 Langkah */}
          <div style={{ marginTop: 70, textAlign: 'left', backgroundColor: '#1e293b', borderRadius: 16, padding: 32, border: '1px solid #334155' }}>
            <h3 style={{ fontSize: 20, fontWeight: 700, marginBottom: 20, color: '#f1f5f9' }}>
              📋 Panduan Penggunaan Client:
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 20 }}>
              <div style={{ backgroundColor: '#0f172a', padding: 20, borderRadius: 12, border: '1px solid #334155' }}>
                <div style={{ color: '#60a5fa', fontWeight: 700, fontSize: 14, marginBottom: 8 }}>LANGKAH 1</div>
                <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 6 }}>Download Installer</div>
                <div style={{ fontSize: 13, color: '#94a3b8' }}>Klik tombol download di atas untuk mengunduh file setup installer (.exe).</div>
              </div>

              <div style={{ backgroundColor: '#0f172a', padding: 20, borderRadius: 12, border: '1px solid #334155' }}>
                <div style={{ color: '#60a5fa', fontWeight: 700, fontSize: 14, marginBottom: 8 }}>LANGKAH 2</div>
                <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 6 }}>Install di Komputer</div>
                <div style={{ fontSize: 13, color: '#94a3b8' }}>Buka file .exe dan ikuti panduan install. Semua komponen otomatis disiapkan.</div>
              </div>

              <div style={{ backgroundColor: '#0f172a', padding: 20, borderRadius: 12, border: '1px solid #334155' }}>
                <div style={{ color: '#60a5fa', fontWeight: 700, fontSize: 14, marginBottom: 8 }}>LANGKAH 3</div>
                <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 6 }}>Login 1x Saja</div>
                <div style={{ fontSize: 13, color: '#94a3b8' }}>Klik tombol Login di aplikasi, masuk di browser yang muncul, lalu simpan session.</div>
              </div>

              <div style={{ backgroundColor: '#0f172a', padding: 20, borderRadius: 12, border: '1px solid #334155' }}>
                <div style={{ color: '#60a5fa', fontWeight: 700, fontSize: 14, marginBottom: 8 }}>LANGKAH 4</div>
                <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 6 }}>Auto-Scrape & Update</div>
                <div style={{ fontSize: 13, color: '#94a3b8' }}>Klik tombol WOW / MTD / Products. Aplikasi otomatis memperbarui diri jika ada versi baru.</div>
              </div>
            </div>
          </div>
        </main>
      </div>
    );
  }

  // ==========================================
  // VIEW: DESKTOP CLIENT (ELECTRON APP)
  // ==========================================
  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#0f172a', color: '#f8fafc', fontFamily: 'system-ui, -apple-system, sans-serif', display: 'flex', flexDirection: 'column' }}>
      {/* Banner Notifikasi Auto-Update */}
      {updateInfo.status === 'downloading' && (
        <div style={{ backgroundColor: '#1e3a8a', color: '#93c5fd', padding: '10px 24px', fontSize: 14, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>🔄 {updateInfo.message}</span>
          <div style={{ width: 140, height: 8, backgroundColor: '#172554', borderRadius: 4, overflow: 'hidden' }}>
            <div style={{ width: `${updateInfo.percent}%`, height: '100%', backgroundColor: '#3b82f6', transition: 'width 0.3s' }}></div>
          </div>
        </div>
      )}

      {updateInfo.status === 'ready' && (
        <div style={{ backgroundColor: '#065f46', color: '#a7f3d0', padding: '10px 24px', fontSize: 14, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>🎉 {updateInfo.message} Restart aplikasi untuk memakai versi baru.</span>
          <button
            onClick={handleApplyUpdate}
            style={{ backgroundColor: '#10b981', color: '#064e3b', fontWeight: 700, border: 'none', padding: '6px 16px', borderRadius: 8, cursor: 'pointer' }}
          >
            Restart & Update Sekarang
          </button>
        </div>
      )}

      {/* Header Aplikasi */}
      <header style={{ borderBottom: '1px solid #1e293b', padding: '16px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 10 }}>
            <span>🍃</span>
            <span>CHAGEE Scraping Dashboard</span>
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: 12, color: '#64748b' }}>
            Aplikasi Desktop Automasi Scraper ke Google Sheets • Versi {appVersion}
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            onClick={() => window.electron?.checkForUpdates?.()}
            style={{ backgroundColor: '#1e293b', border: '1px solid #334155', color: '#94a3b8', padding: '6px 14px', borderRadius: 8, fontSize: 12, cursor: 'pointer' }}
          >
            Periksa Update
          </button>
        </div>
      </header>

      {/* Main Content Dashboard */}
      <div style={{ flex: 1, padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* Card Status Login Shared */}
        <div style={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: 12, padding: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                <span style={{ fontSize: 14, fontWeight: 600, color: '#94a3b8' }}>Status Session:</span>
                {isLoggedIn ? (
                  <span style={{ backgroundColor: '#065f46', color: '#6ee7b7', padding: '4px 12px', borderRadius: 20, fontSize: 13, fontWeight: 700 }}>
                    ✅ Sudah Login (Shared Session Aktif)
                  </span>
                ) : (
                  <span style={{ backgroundColor: '#7f1d1d', color: '#fca5a5', padding: '4px 12px', borderRadius: 20, fontSize: 13, fontWeight: 700 }}>
                    ❌ Belum Login
                  </span>
                )}
              </div>
              <div style={{ fontSize: 11, color: '#64748b', wordBreak: 'break-all' }}>
                Lokasi Session: <code>{userDataInfo.storagePath || 'Memuat...'}</code>
              </div>
            </div>

            {/* Tombol Kontrol Login */}
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button
                onClick={() => handleRun('Login')}
                disabled={Boolean(runningJob)}
                style={{
                  backgroundColor: '#2563eb',
                  color: '#ffffff',
                  border: 'none',
                  padding: '10px 18px',
                  borderRadius: 8,
                  fontWeight: 600,
                  fontSize: 13,
                  cursor: runningJob ? 'not-allowed' : 'pointer',
                  opacity: runningJob ? 0.6 : 1
                }}
              >
                {runningJob === 'Login' ? 'Membuka Browser Login...' : '🔑 Buka Browser Login'}
              </button>

              <button
                onClick={handleSaveSession}
                style={{
                  backgroundColor: '#059669',
                  color: '#ffffff',
                  border: 'none',
                  padding: '10px 18px',
                  borderRadius: 8,
                  fontWeight: 600,
                  fontSize: 13,
                  cursor: 'pointer'
                }}
              >
                💾 Simpan Session ke Shared
              </button>

              <button
                onClick={handleRefreshLogin}
                style={{ backgroundColor: '#334155', color: '#cbd5e1', border: 'none', padding: '10px 14px', borderRadius: 8, fontSize: 13, cursor: 'pointer' }}
                title="Cek Ulang Status File Session"
              >
                🔄
              </button>

              {isLoggedIn && (
                <button
                  onClick={handleLogout}
                  style={{ backgroundColor: '#451a03', color: '#fdba74', border: '1px solid #78350f', padding: '10px 14px', borderRadius: 8, fontSize: 13, cursor: 'pointer' }}
                >
                  Logout
                </button>
              )}
            </div>
          </div>

          {saveTriggerStatus && (
            <div style={{ marginTop: 12, fontSize: 13, color: '#38bdf8' }}>
              {saveTriggerStatus}
            </div>
          )}
        </div>

        {/* Card Pemilihan Folder Kerja */}
        <div style={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: 12, padding: 18, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#94a3b8', marginBottom: 4 }}>Folder Kerja / Target Store:</div>
            <div style={{ fontSize: 14, color: folder ? '#f1f5f9' : '#64748b', fontWeight: 500 }}>
              {folder || 'Belum dipilih (Wajib untuk Products / Download Store)'}
            </div>
          </div>
          <button
            onClick={handleSelectFolder}
            style={{ backgroundColor: '#334155', border: '1px solid #475569', color: '#f8fafc', padding: '8px 16px', borderRadius: 8, fontSize: 13, cursor: 'pointer', fontWeight: 600 }}
          >
            📁 Pilih Folder Lokal
          </button>
        </div>

        {/* Tombol Eksekusi Scraper */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14 }}>
          <button
            onClick={() => handleRun('WOW')}
            disabled={!isLoggedIn || Boolean(runningJob)}
            style={{
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              padding: '18px 20px',
              borderRadius: 12,
              textAlign: 'left',
              cursor: !isLoggedIn || runningJob ? 'not-allowed' : 'pointer',
              opacity: !isLoggedIn || runningJob ? 0.5 : 1
            }}
          >
            <div style={{ fontSize: 16, fontWeight: 700, color: '#38bdf8', marginBottom: 4 }}>
              {runningJob === 'WOW' ? '⏳ Sedang Berjalan...' : '▶ Jalankan WOW'}
            </div>
            <div style={{ fontSize: 12, color: '#94a3b8' }}>Scrape WOW Dashboard & kirim ke Google Sheets</div>
          </button>

          <button
            onClick={() => handleRun('MTD')}
            disabled={!isLoggedIn || Boolean(runningJob)}
            style={{
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              padding: '18px 20px',
              borderRadius: 12,
              textAlign: 'left',
              cursor: !isLoggedIn || runningJob ? 'not-allowed' : 'pointer',
              opacity: !isLoggedIn || runningJob ? 0.5 : 1
            }}
          >
            <div style={{ fontSize: 16, fontWeight: 700, color: '#38bdf8', marginBottom: 4 }}>
              {runningJob === 'MTD' ? '⏳ Sedang Berjalan...' : '▶ Jalankan MTD'}
            </div>
            <div style={{ fontSize: 12, color: '#94a3b8' }}>Scrape MTD ke Google Sheets</div>
          </button>

          <button
            onClick={() => handleRun('Download store')}
            disabled={!isLoggedIn || Boolean(runningJob)}
            style={{
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              padding: '18px 20px',
              borderRadius: 12,
              textAlign: 'left',
              cursor: !isLoggedIn || runningJob ? 'not-allowed' : 'pointer',
              opacity: !isLoggedIn || runningJob ? 0.5 : 1
            }}
          >
            <div style={{ fontSize: 16, fontWeight: 700, color: '#38bdf8', marginBottom: 4 }}>
              {runningJob === 'Download store' ? '⏳ Sedang Mengunduh...' : '📥 Download Store'}
            </div>
            <div style={{ fontSize: 12, color: '#94a3b8' }}>Unduh data Excel per toko dari Dashboard</div>
          </button>

          <button
            onClick={() => handleRun('Products')}
            disabled={Boolean(runningJob)}
            style={{
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              padding: '18px 20px',
              borderRadius: 12,
              textAlign: 'left',
              cursor: runningJob ? 'not-allowed' : 'pointer',
              opacity: runningJob ? 0.5 : 1
            }}
          >
            <div style={{ fontSize: 16, fontWeight: 700, color: '#38bdf8', marginBottom: 4 }}>
              {runningJob === 'Products' ? '⏳ Sedang Memproses...' : '📊 Rekap Products'}
            </div>
            <div style={{ fontSize: 12, color: '#94a3b8' }}>Olah file Excel toko & kirim ke Summary Sheet</div>
          </button>
        </div>

        {/* Real-time Log Viewer */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', backgroundColor: '#020617', border: '1px solid #1e293b', borderRadius: 12, overflow: 'hidden' }}>
          <div style={{ padding: '10px 16px', borderBottom: '1px solid #1e293b', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', letterSpacing: '0.5px' }}>TERMINAL LOGS REAL-TIME</span>
            <button
              onClick={() => setLogs('')}
              style={{ backgroundColor: 'transparent', border: 'none', color: '#64748b', fontSize: 12, cursor: 'pointer' }}
            >
              Bersihkan Log
            </button>
          </div>
          <pre
            ref={logContainerRef}
            style={{
              flex: 1,
              margin: 0,
              padding: 16,
              color: '#4ade80',
              fontFamily: 'Consolas, "Fira Code", monospace',
              fontSize: 12.5,
              lineHeight: 1.5,
              overflowY: 'auto',
              minHeight: 250,
              maxHeight: 400,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all'
            }}
          >
            {logs || '> Menunggu perintah... Pilih login atau jalankan salah satu scraper.'}
          </pre>
        </div>
      </div>
    </div>
  );
}
