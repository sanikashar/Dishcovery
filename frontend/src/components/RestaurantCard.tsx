import { MapPin } from "lucide-react";

export interface Restaurant {
  id: number;
  name: string;
  city: string;
  matchScore?: number;
  mood: string;
// for potential future use
//   cuisine: string[];
//   rating: number;
//   reviews: number;
//   priceRange: string;
//   ambience: string[];
//   hours: string;
//   serviceType: string[];
//   description: string;
}

interface RestaurantCardProps {
  restaurant: Restaurant;
}

export function RestaurantCard({ restaurant }: RestaurantCardProps) {
  return (
    <div className="bg-white rounded-3xl p-6 shadow-md border-2 border-red-100 hover:border-red-300 hover:shadow-lg transition-all duration-300">
      <div className="flex justify-between items-start">
        <div className="flex-1">
          <h3 className="text-xl mb-2 text-gray-800">{restaurant.name}</h3>
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <MapPin className="size-4" />
            <span>{restaurant.city}</span>
          </div>
        </div>
        {restaurant.matchScore !== undefined && (
          <div className="bg-gradient-to-br from-red-500 to-rose-600 text-white px-4 py-2 rounded-full text-sm font-medium shadow-sm">
            {Math.round(restaurant.matchScore * 100)}% match
          </div>
        )}
      </div>
    </div>
  );
}