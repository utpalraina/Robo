import type { Metadata } from 'next';
import './globals.css';
import Sidebar from '@/components/layout/Sidebar';
import ChatPanel from '@/components/chat/ChatPanel';

export const metadata: Metadata = {
  title: 'Planetary Trading System',
  description: 'Market analysis using planetary cycles and Gann methodology',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-bg-primary text-text-primary min-h-screen">
        <div className="flex">
          <Sidebar />
          <main className="flex-1 ml-[240px] min-h-screen">
            {children}
          </main>
        </div>
        <ChatPanel />
      </body>
    </html>
  );
}
