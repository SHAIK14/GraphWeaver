"use client";

import React from 'react';

const Logo = ({ className = "w-8 h-8" }) => {
  return (
    <div className={`${className} flex items-center justify-center`}>
      <svg
        viewBox="0 0 100 100"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-full h-full"
      >
        {/* The Weave - Bold Interlocking Data Strands */}
        {/* Horizontal Strand */}
        <path
          d="M10 42 H90"
          stroke="#212121"
          strokeWidth="10"
          strokeLinecap="round"
        />
        <path
          d="M10 58 H90"
          stroke="#212121"
          strokeWidth="10"
          strokeLinecap="round"
        />

        {/* Diagonal Strand 1 (Interlocked) */}
        <path
          d="M25 15 L75 85"
          stroke="#212121"
          strokeWidth="10"
          strokeLinecap="round"
        />
        {/* Diagonal Strand 2 (Interlocked) */}
        <path
          d="M75 15 L25 85"
          stroke="#212121"
          strokeWidth="10"
          strokeLinecap="round"
        />

        {/* Neural Nodes - Solid Connections */}
        <circle cx="50" cy="50" r="14" fill="#212121" />
        <circle cx="34" cy="22" r="6" fill="#212121" />
        <circle cx="66" cy="22" r="6" fill="#212121" />
        <circle cx="34" cy="78" r="6" fill="#212121" />
        <circle cx="66" cy="78" r="6" fill="#212121" />
        <circle cx="15" cy="50" r="6" fill="#212121" />
        <circle cx="85" cy="50" r="6" fill="#212121" />

        {/* High-Contrast Separation Cuts (Digital Weave effect) */}
        <path d="M44 50 H56" stroke="#fafafa" strokeWidth="3" />
        <path d="M44 38 L48 44" stroke="#fafafa" strokeWidth="3" />
        <path d="M52 56 L56 62" stroke="#fafafa" strokeWidth="3" />
      </svg>
    </div>
  );
};

export default Logo;
