import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'EBCO Private Limited — Data Analyst',
  description: 'EBCO Private Limited · fully-local data-analysis agent — upload a CSV, ask in plain English.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">{children}</body>
    </html>
  )
}
