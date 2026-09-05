import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Schedule Lab — Amherst Soccer',
  description: 'Explore opponents, compare schedules, and understand NCAA Division III NPI tradeoffs.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
