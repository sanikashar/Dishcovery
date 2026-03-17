import { Search } from "lucide-react";
import { Input } from "./input";

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export function SearchBar({ value, onChange, placeholder }: SearchBarProps) {
  return (
    <div className="relative w-full">
      <Search className="absolute left-4 top-1/2 -translate-y-1/2 size-5 text-red-400" />
      <Input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder || "Search for cravings, cuisines, or vibes..."}
        className="pl-12 h-14 text-base rounded-full border-2 border-red-200 focus:border-red-400 transition-colors shadow-sm"
      />
    </div>
  );
}