import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'AI Agent School',
  description: 'University-style platform for AI agent education',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
