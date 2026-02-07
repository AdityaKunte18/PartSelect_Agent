import React from 'react';
import Image from 'next/image';
import { ShoppingCart, Search, User } from 'lucide-react';

export default function Header() {
  
    return (
        <header className="w-full font-sans">
    <div className="bg-[#347878] text-white text-xs py-2 px-4 flex justify-between items-center">
        <div className="hidden md:flex gap-4 hover:text-gray-300 cursor-pointer">
        <span className="font-bold">1-866-319-8402</span>
       
      </div>
      <div className="hidden md:flex gap-4 hover:text-gray-300 transition-colors cursor-pointer ml-5">
        
        <span>Your Orders</span>
      </div>
      <div className="flex gap-4 ml-auto">
      </div>
    </div>

    
    <div className="bg-white border-b border-gray-200 py-4 px-4 md:px-8 flex flex-col md:flex-row items-center gap-4">
    
      <div className="flex items-center gap-2">
        <Image
          src="/logo.svg"
          alt="PartSelect"
          width={140}
          height={100}
          priority
          className="h-15 w-auto"
        />
        <span className="sr-only">PartSelect</span>
      </div>

      {/* Header Search Bar */}
      <div className="flex-1 w-full max-w-2xl flex">
        <input 
          type="text" 
          placeholder="Search model or part number" 
          className="w-full border border-gray-300 rounded-l-md px-4 py-2 focus:outline-none focus:border-[#347878]"
        />
      
        <button className="bg-[#347878] text-white font-bold px-6 py-2 rounded-r-md hover:bg-[#2a6161] transition-colors flex items-center gap-2">
          <Search size={20} />
        </button>
      </div>

      
      <div className="flex items-center gap-6 text-[#347878]">
        <div className="flex flex-col items-center cursor-pointer hover:text-black transition-colors">
          <User size={24} />
          <span className="text-xs mt-1">Account</span>
        </div>
        <div className="flex flex-col items-center cursor-pointer hover:text-black transition-colors">
          <ShoppingCart size={24} />
          <span className="text-xs mt-1">Cart</span>
        </div>
      </div>
    </div>

 {/* nav bar */}
    <nav className="bg-[#F4F4F4] text-[#333] py-2 px-4 md:px-8 border-b border-gray-300 overflow-x-auto">
      <ul className="flex gap-6 text-sm font-bold whitespace-nowrap">
        <li className="cursor-pointer hover:text-[#347878]">Departments</li>
        <li className="cursor-pointer hover:text-[#347878]">Brands</li>
        <li className="cursor-pointer hover:text-[#347878]">Blog</li>
        <li className="cursor-pointer hover:text-[#347878]">Repair Help</li>
      </ul>
    </nav>
  </header>
  );
}
