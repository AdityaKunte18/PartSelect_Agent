// app/page.js
import Header from './components/Header'; 
import Footer from './components/Footer'; 
import ChatWidget from './components/ChatWidget';

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col bg-white font-sans text-gray-800">
      <Header />
      <main className="flex-1 container mx-auto px-4 py-12">
        
      </main>
      <Footer />
      <ChatWidget />
    </div>
  );
}