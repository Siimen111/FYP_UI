const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('vtrack', {
  platform: process.platform,
});
