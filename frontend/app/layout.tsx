import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'TransactionGuard | Database Anomaly & Concurrency Assurance Platform',
  description: 'Enterprise developer platform for reproducing, detecting, investigating and preventing database transaction anomalies.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-slate-950 text-slate-100 min-h-screen font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
