import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";
import { AlertDock } from "@/components/AlertModal";

export const metadata: Metadata = {
  title: "Agentic Chase",
  description: "Multi-agent chat intelligence & automation",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="min-w-0 flex-1 p-6 lg:p-8">{children}</main>
        </div>
        <AlertDock />
      </body>
    </html>
  );
}
