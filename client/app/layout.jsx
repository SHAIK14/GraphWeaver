import { Inter, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const mono = IBM_Plex_Mono({
  weight: ["400", "500"],
  subsets: ["latin"],
  variable: "--font-ibm-plex-mono",
});

export const metadata = {
  title: "GraphWeaver | Precise Knowledge Engineering",
  description: "Enterprise-grade knowledge graph construction and reasoning engine.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} ${mono.variable} antialiased text-[#212121]`} suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
