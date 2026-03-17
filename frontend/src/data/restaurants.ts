// hardcoded for now, the restaurant data should come from backend
import { Restaurant } from "../components/RestaurantCard";

export const restaurants: Restaurant[] = [
  {
    id: 1,
    name: "Bella Italia Trattoria",
    city: "Boston",
    matchScore: 0.92,
    mood: "casual"
  },
  {
    id: 2,
    name: "Sakura Sushi & Ramen",
    city: "San Francisco",
    matchScore: 0.87,
    mood: "upscale"
  },
];