'use strict';

import { app, protocol, BrowserWindow, Tray, Menu } from 'electron';
import {
  createProtocol,
  installVueDevtools
} from 'vue-cli-plugin-electron-builder/lib';
import { join } from 'path';
const isDevelopment = process.env.NODE_ENV !== 'production';

// Keep a global reference of the window object, if you don't, the window will
// be closed automatically when the JavaScript object is garbage collected.
let win: BrowserWindow | undefined;
let tray: Tray | undefined;

if (!isDevelopment && !app.requestSingleInstanceLock()) {
  app.quit();
}

// Scheme must be registered before the app is ready
protocol.registerSchemesAsPrivileged([{ scheme: 'app' }]);

app.on('second-instance', (event, commandLine, workingDirectory) => {
  const win = ensureWindow();
  win.restore();
  win.focus();
});

function ensureWindow(): BrowserWindow {
  if (win) {
    return win;
  }
  // Create the browser window.
  win = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      nodeIntegration: true
    }
  });
  const ret = win;

  ret.setMenu(null);

  if (process.env.WEBPACK_DEV_SERVER_URL) {
    // Load the url of the dev server if in development mode
    ret.loadURL(process.env.WEBPACK_DEV_SERVER_URL);
    if (!process.env.IS_TEST) ret.webContents.openDevTools();
  } else {
    createProtocol('app');
    // Load the index.html when not in development
    ret.loadURL('app://./index.html');
  }

  ret.on('closed', () => {
    win = undefined;
  });

  ret.on('close', event => {
    event.preventDefault();
    ret.hide();
    console.log(arguments);
    ensureTray().displayBalloon({
      title: 'NukeBatchRender',
      content: '已隐藏至托盘'
    });
  });

  return ret;
}

function ensureTray(): Tray {
  if (tray) {
    return tray;
  }

  tray = new Tray(join(__static, 'favicon.ico'));
  tray.setToolTip('NukeBatchRender');
  tray.setContextMenu(
    Menu.buildFromTemplate([
      {
        label: '显示',
        click() {
          ensureWindow().show();
        }
      },
      {
        label: '退出',
        click() {
          if (win) win.destroy();
          app.quit();
        }
      }
    ])
  );
  tray.on('double-click', () => {
    ensureWindow().show();
  });

  return tray;
}

// Quit when all windows are closed.
app.on('window-all-closed', () => {
  // On macOS it is common for applications and their menu bar
  // to stay active until the user quits explicitly with Cmd + Q
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  // On macOS it's common to re-create a window in the app when the
  // dock icon is clicked and there are no other windows open.
  ensureWindow();
});

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.on('ready', async () => {
  if (isDevelopment && !process.env.IS_TEST) {
    // Install Vue Devtools
    try {
      await installVueDevtools();
    } catch (e) {
      console.error('Vue Devtools failed to install:', e.toString());
    }
  }

  ensureTray();
  ensureWindow();
});

// Exit cleanly on request from parent process in development mode.
if (isDevelopment) {
  if (process.platform === 'win32') {
    process.on('message', data => {
      if (data === 'graceful-exit') {
        app.quit();
      }
    });
  } else {
    process.on('SIGTERM', () => {
      console.log(1);
      app.quit();
    });
  }
}
