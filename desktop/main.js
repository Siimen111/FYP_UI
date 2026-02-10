const { app, BrowserWindow } = require('electron');
const path = require('path');

const resolveView = () => {
  const arg = process.argv.find(value => value.startsWith('--view='));
  const view = (
    process.env.VTRACK_VIEW || (arg ? arg.split('=')[1] : '')
  ).toLowerCase();
  if (view === 'lawyer') {
    return 'lawyer.html';
  }
  return 'index.html';
};

const createWindow = () => {
  const win = new BrowserWindow({
    width: 1200,
    height: 820,
    backgroundColor: '#f2efe9',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  const viewFile = resolveView();
  win.loadFile(path.join(__dirname, 'renderer', viewFile));
};

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
