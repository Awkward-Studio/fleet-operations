import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Index Fleet",
  description: "Fleet operations, driver availability, and trip dispatch dashboard"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

