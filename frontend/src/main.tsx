import React from 'react'
import ReactDOM from 'react-dom/client'
import { Toaster } from 'react-hot-toast'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Toaster
      position="top-center"
      gutter={10}
      toastOptions={{
        duration: 4500,
        style: {
          borderRadius: '16px',
          background: '#ffffff',
          color: '#1e293b',
          padding: '12px 16px',
          fontSize: '14px',
          fontWeight: 500,
          boxShadow: '0 1px 2px 0 rgba(11,40,25,0.06), 0 12px 28px -8px rgba(11,40,25,0.18)',
          border: '1px solid rgb(241 245 249)',
          maxWidth: '420px',
        },
        success: {
          duration: 3500,
          iconTheme: { primary: '#16a34f', secondary: '#ffffff' },
          style: { border: '1px solid #dcfce9' },
        },
        error: {
          duration: 6000,
          iconTheme: { primary: '#e12f52', secondary: '#ffffff' },
          style: { border: '1px solid #ffe1e4' },
        },
        loading: {
          iconTheme: { primary: '#22c569', secondary: '#ffffff' },
        },
      }}
    />
    <App />
  </React.StrictMode>
)
