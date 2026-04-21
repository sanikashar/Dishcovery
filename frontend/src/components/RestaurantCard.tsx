import { ChevronDown, ChevronUp, Clock, DollarSign, MapPin, Sparkles, Star, UtensilsCrossed } from "lucide-react";
import { useState } from "react";

export interface DimensionSignal {
  dim_index: number;
  dimension_label: string;
  contribution?: number;
  display_label?: string;
}

export interface Restaurant {
  business_id: string;
  name: string;
  address?: string | string[];
  city: string;
  state?: string;
  postal_code?: string;
  matchScore?: number;
  cuisine?: string[];
  categories?: string | string[];
  rating?: number;
  stars?: number;
  priceRange?: string;
  priceTier?: number | null;
  ambience?: string[];
  hours?: Record<string, string> | null;
  relevantTags?: string[];
  svd_positive_dimensions?: DimensionSignal[];
  svd_negative_dimensions?: DimensionSignal[];
}

interface RestaurantCardProps {
  restaurant: Restaurant;
  query?: string;
  querySignals?: string[];
}

const GENERIC_CATEGORIES = new Set([
  "Restaurants",
  "Nightlife",
  "Food",
  "Bars",
  "Desserts",
  "Vegetarian",
  "Event Planning & Services",
  "Arts & Entertainment",
  "Local Services",
  "Shopping",
  "Specialty Food",
  "Caterers",
  "Active Life",
  "Beauty & Spas",
  "Hotels & Travel",
]);

export function RestaurantCard({ restaurant, query, querySignals = [] }: RestaurantCardProps) {
  const [explainOpen, setExplainOpen] = useState(false);
  const [llmExplanation, setLlmExplanation] = useState<string | null>(null);
  const [explainLoading, setExplainLoading] = useState(false);
  const [explainError, setExplainError] = useState(false);

  const handleExplainToggle = async () => {
    const next = !explainOpen;
    setExplainOpen(next);
    if (next && llmExplanation === null && !explainLoading && !explainError) {
      setExplainLoading(true);
      try {
        const res = await fetch("/api/explain", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ business_id: restaurant.business_id, query: query ?? "" }),
        });
        const json = await res.json();
        if (json.explanation) {
          setLlmExplanation(json.explanation);
        } else {
          setExplainError(true);
        }
      } catch {
        setExplainError(true);
      } finally {
        setExplainLoading(false);
      }
    }
  };

  const categoriesList = Array.isArray(restaurant.categories)
    ? restaurant.categories
    : typeof restaurant.categories === "string"
      ? restaurant.categories.split(",").map((item) => item.trim()).filter(Boolean)
      : [];

  const cuisineCandidates = [
    ...(restaurant.cuisine ?? []),
    ...categoriesList,
  ];
  const primaryCuisine = cuisineCandidates.find((cat) => cat && !GENERIC_CATEGORIES.has(cat));
  // All displayable tags: ambience terms + every non-generic category that isn't already shown as the cuisine label in the row above.
  const ambienceTags = restaurant.ambience ?? [];
  const categoryTags = categoriesList.filter(
    (cat) => !GENERIC_CATEGORIES.has(cat) && cat !== primaryCuisine,
  );
  const derivedTags = [...new Set([...ambienceTags, ...categoryTags])];

  const relevantSet = new Set(
    (restaurant.relevantTags ?? []).map((t) => t.toLowerCase()),
  );
  const hasRelevantTags = relevantSet.size > 0;

  const priceDisplay =
    restaurant.priceRange ??
    (restaurant.priceTier && restaurant.priceTier > 0 ? "$".repeat(restaurant.priceTier) : undefined);

  const userTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const todayLabel = new Intl.DateTimeFormat("en-US", { weekday: "long", timeZone: userTimeZone }).format(new Date());

  const parseTime = (timeStr: string): string | null => {
    const [hourRaw, minuteRaw = "0"] = timeStr.split(":");
    const hourNum = Number(hourRaw);
    const minuteNum = Number(minuteRaw);
    if (Number.isNaN(hourNum) || Number.isNaN(minuteNum)) return null;
    const period = hourNum >= 12 ? "PM" : "AM";
    const hour12 = ((hourNum + 11) % 12) + 1;
    return `${hour12}:${minuteNum.toString().padStart(2, "0")} ${period}`;
  };

  const formatHoursForToday = (): string | null => {
    if (!restaurant.hours || typeof restaurant.hours !== "object") return null;
    const todayRange = restaurant.hours[todayLabel];
    if (!todayRange) return null;
    if (todayRange.toLowerCase() === "closed") return "Closed today";
    const [start, end] = todayRange.split("-");
    if (!start || !end) return null;
    if (start === "0:0" && end === "0:0") return "Closed today";
    const startFormatted = parseTime(start);
    const endFormatted = parseTime(end);
    if (!startFormatted || !endFormatted) return null;
    return `${startFormatted} – ${endFormatted}`;
  };

  const todayHours = formatHoursForToday();

  const ratingValue = restaurant.rating ?? restaurant.stars;
  const street =
    Array.isArray(restaurant.address)
      ? restaurant.address.filter(Boolean).join(", ")
      : restaurant.address?.trim();
  const location = street ? `${street}, ${restaurant.city}` : restaurant.city;

  const effectiveQuerySignals = querySignals;
  const positiveSignals = restaurant.svd_positive_dimensions ?? [];
  const negativeSignals = restaurant.svd_negative_dimensions ?? [];
  const prettySignal = (label: string): string => label.replace(/\s*\/\s*/g, " / ").trim();
  const showSignal = (signal: DimensionSignal): string => signal.display_label ?? signal.dimension_label;

  return (
    <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200 hover:shadow-md transition-all duration-200">
      {/* Header: Restaurant Name + Match Score */}
      <div className="flex justify-between items-start mb-3">
        <h3 className="text-xl text-gray-900">{restaurant.name}</h3>
        {restaurant.matchScore !== undefined && (
          <div className="bg-red-50 text-red-600 px-3 py-1 rounded-full text-sm">
            {Math.round(restaurant.matchScore * 100)}% match
          </div>
        )}
      </div>

      {/* Location */}
      <div className="flex items-center gap-2 mb-4 text-sm text-gray-600">
        <MapPin className="size-4 text-gray-400" />
        <span>{location}</span>
      </div>

      {/* Metadata Row with Icons */}
      <div className="flex flex-wrap items-center gap-4 mb-4 text-sm text-gray-600">
        {ratingValue !== undefined && (
          <div className="flex items-center gap-1.5">
            <Star className="size-4 text-yellow-500 fill-yellow-500" />
            <span>{ratingValue.toFixed(1)}</span>
          </div>
        )}
        {priceDisplay && (
          <div className="flex items-center gap-1.5">
            <DollarSign className="size-4 text-gray-400" />
            <span>{priceDisplay}</span>
          </div>
        )}
        {primaryCuisine && (
          <div className="flex items-center gap-1.5">
            <UtensilsCrossed className="size-4 text-gray-400" />
            <span>{primaryCuisine}</span>
          </div>
        )}
        {todayHours && (
          <div className="flex items-center gap-1.5">
            <Clock className="size-4 text-gray-400" />
            <span>{todayHours}</span>
          </div>
        )}
      </div>

      {/* Tags / Pills */}
      <div className="flex flex-wrap gap-2">
        {(() => {
          const coloredStyles = [
            "px-3 py-1 bg-red-50 text-red-700 border border-red-200 rounded-full text-sm",
            "px-3 py-1 bg-rose-50 text-rose-700 border border-rose-200 rounded-full text-sm",
            "px-3 py-1 bg-pink-50 text-pink-700 border border-pink-200 rounded-full text-sm",
          ];
          const dimStyle = "px-3 py-1 bg-white text-gray-600 border border-gray-200 rounded-full text-sm";
          let colorIndex = 0;
          return derivedTags.map((tag, index) => {
            const isRelevant = hasRelevantTags && relevantSet.has(tag.toLowerCase());
            const className = isRelevant
              ? coloredStyles[colorIndex++ % coloredStyles.length]
              : dimStyle;
            return <span key={index} className={className}>{tag}</span>;
          });
        })()}
      </div>

      {/* Why this result? */}
      {/* Debugged with limited help from GenAI. */}
      {query && (
        <div className="mt-4 border-t border-gray-100 pt-3">
          <button
            onClick={handleExplainToggle}
            className="flex items-center gap-1.5 text-sm text-red-500 hover:text-red-700 transition-colors"
          >
            <Sparkles className="size-3.5" />
            <span>Why this result?</span>
            {explainOpen ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
          </button>

          {explainOpen && (
            <div className="mt-3 space-y-4">
              <div className="px-3 py-2.5 bg-red-50 border border-red-100 rounded-xl text-sm text-gray-700 leading-relaxed">
                {explainLoading && (
                  <span className="text-gray-400 italic">Generating explanation…</span>
                )}
                {!explainLoading && llmExplanation && llmExplanation}
                {!explainLoading && explainError && (
                  <span className="text-gray-400 italic">Unable to generate explanation.</span>
                )}
              </div>

              {(effectiveQuerySignals.length > 0 || positiveSignals.length > 0 || negativeSignals.length > 0) && (
                <div className="space-y-4">
                  <p className="text-xs text-gray-500">
                    These are the top SVD themes learned from the reviews that influenced the match score for this restaurant. 
                  </p>

                  {effectiveQuerySignals.length > 0 && (
                    <div>
                      <p className="text-sm text-gray-700 mb-2">Query Dimensions:</p>
                      <div className="flex flex-wrap gap-2">
                        {effectiveQuerySignals.slice(0, 3).map((sig, index) => (
                          <span
                            key={`${sig}-${index}`}
                            className="px-3 py-1 bg-purple-50 text-purple-700 border border-purple-200 rounded-full text-sm"
                            title={sig}
                          >
                            {prettySignal(sig)}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {positiveSignals.length > 0 && (
                    <div>
                      <p className="text-sm text-gray-700 mb-2">Positive Dimensions:</p>
                      <div className="flex flex-wrap gap-2">
                        {positiveSignals.slice(0, 3).map((d) => (
                          <span
                            key={d.dim_index}
                            className="px-3 py-1 bg-pink-50 text-pink-700 border border-pink-200 rounded-full text-sm"
                            title={showSignal(d)}
                          >
                            {prettySignal(showSignal(d))}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {negativeSignals.length > 0 && (
                    <div>
                      <p className="text-sm text-gray-700 mb-2">Negative Dimensions:</p>
                      <div className="flex flex-wrap gap-2">
                        {negativeSignals.slice(0, 3).map((d) => (
                          <span
                            key={d.dim_index}
                            className="px-3 py-1 bg-yellow-50 text-orange-700 border border-orange-300 rounded-full text-sm"
                            title={showSignal(d)}
                          >
                            {prettySignal(showSignal(d))}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
