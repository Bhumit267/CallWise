import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/contexts/auth-context';

export const metadata: Metadata = {
  title: 'Callwise - AI Voice Receptionist',
  description: 'Manage your AI voice receptionist, appointments, calls, and knowledge base.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#fbfaf6] text-black antialiased selection:bg-[#ffe600] selection:text-black font-sans">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
