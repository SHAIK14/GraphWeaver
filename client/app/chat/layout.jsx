import Sidebar from '@/components/layout/Sidebar';

export default function ChatLayout({ children }) {
  return (
    <div className="flex h-screen overflow-hidden bg-[#fcfaf7]">
      <Sidebar />
      <main className="flex-1 ml-[240px] flex overflow-hidden">
        {children}
      </main>
    </div>
  );
}
