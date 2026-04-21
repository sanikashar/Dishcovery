/**
 * Maps search keywords to category/ambience strings from init.json.
 * Used to highlight relevant tag pills on each result card.
 */
const keywordMap: Record<string, string[]> = {
  // map created with limited help from Gen AI
  // ── American / comfort ────────────────────────────────────────────────────
  american:      ["American (Traditional)", "American (New)"],
  burger:        ["Burgers", "American (Traditional)", "American (New)"],
  burgers:       ["Burgers", "American (Traditional)", "American (New)"],
  cheesesteak:   ["Cheesesteaks"],
  cheesesteaks:  ["Cheesesteaks"],
  comfort:       ["Comfort Food"],
  diner:         ["Diners"],
  hotdog:        ["Hot Dogs"],
  hotdogs:       ["Hot Dogs"],
  southern:      ["Southern", "Soul Food"],
  soul:          ["Soul Food"],
  cajun:         ["Cajun/Creole"],
  creole:        ["Cajun/Creole"],
  smokehouse:    ["Smokehouse"],
  smoke:         ["Smokehouse"],
  texmex:        ["Tex-Mex"],

  // ── European ──────────────────────────────────────────────────────────────
  italian:       ["Italian"],
  pizza:         ["Pizza", "Italian"],
  pasta:         ["Pasta Shops", "Italian"],
  french:        ["French"],
  crepe:         ["Creperies"],
  crepes:        ["Creperies"],
  greek:         ["Greek"],
  spanish:       ["Spanish", "Tapas/Small Plates", "Tapas Bars"],
  tapas:         ["Tapas/Small Plates", "Tapas Bars", "Spanish"],
  german:        ["German"],
  british:       ["British"],
  irish:         ["Irish", "Irish Pub"],
  polish:        ["Polish"],
  portuguese:    ["Portuguese"],
  russian:       ["Russian"],
  scandinavian:  ["Scandinavian"],
  hungarian:     ["Hungarian"],
  belgian:       ["Belgian"],
  ukrainian:     ["Ukrainian"],
  basque:        ["Basque"],
  iberian:       ["Iberian"],

  // ── Asian ─────────────────────────────────────────────────────────────────
  asian:         ["Asian Fusion"],
  japanese:      ["Japanese", "Sushi Bars", "Ramen", "Izakaya"],
  sushi:         ["Sushi Bars", "Japanese"],
  ramen:         ["Ramen", "Japanese", "Noodles"],
  izakaya:       ["Izakaya"],
  chinese:       ["Chinese"],
  cantonese:     ["Cantonese"],
  szechuan:      ["Szechuan"],
  dim:           ["Dim Sum", "Chinese"],
  dimsum:        ["Dim Sum", "Chinese"],
  korean:        ["Korean"],
  thai:          ["Thai"],
  vietnamese:    ["Vietnamese"],
  pho:           ["Vietnamese"],
  indian:        ["Indian"],
  pakistani:     ["Pakistani"],
  bangladeshi:   ["Bangladeshi"],
  afghan:        ["Afghan"],
  malaysian:     ["Malaysian"],
  taiwanese:     ["Taiwanese"],
  filipino:      ["Filipino"],
  indonesian:    ["Indonesian"],
  singaporean:   ["Singaporean"],
  burmese:       ["Burmese"],
  cambodian:     ["Cambodian"],
  laotian:       ["Laotian"],
  mongolian:     ["Mongolian"],
  hotpot:        ["Hot Pot"],

  // ── Middle Eastern / African ──────────────────────────────────────────────
  middleeastern: ["Middle Eastern"],
  lebanese:      ["Lebanese"],
  arabic:        ["Arabic"],
  persian:       ["Persian/Iranian"],
  iranian:       ["Persian/Iranian"],
  turkish:       ["Turkish"],
  moroccan:      ["Moroccan"],
  falafel:       ["Falafel"],
  kebab:         ["Kebab"],
  halal:         ["Halal"],
  kosher:        ["Kosher"],
  ethiopian:     ["Ethiopian"],
  african:       ["African"],
  egyptian:      ["Egyptian"],
  senegalese:    ["Senegalese"],
  somali:        ["Somali"],

  // ── Latin American / Caribbean ────────────────────────────────────────────
  latin:         ["Latin American"],
  mexican:       ["Mexican"],
  taco:          ["Tacos", "Mexican"],
  tacos:         ["Tacos", "Mexican"],
  cuban:         ["Cuban"],
  caribbean:     ["Caribbean"],
  peruvian:      ["Peruvian"],
  brazilian:     ["Brazilian"],
  colombian:     ["Colombian"],
  argentine:     ["Argentine"],
  dominican:     ["Dominican"],
  salvadoran:    ["Salvadoran"],
  honduran:      ["Honduran"],
  haitian:       ["Haitian"],
  venezuelan:    ["Venezuelan"],
  trinidadian:   ["Trinidadian"],
  empanada:      ["Empanadas"],
  empanadas:     ["Empanadas"],

  // ── Mediterranean ─────────────────────────────────────────────────────────
  mediterranean: ["Mediterranean"],

  // ── Seafood ───────────────────────────────────────────────────────────────
  seafood:       ["Seafood"],
  fish:          ["Fish & Chips", "Seafood"],

  // ── Meat / grill ──────────────────────────────────────────────────────────
  steak:         ["Steakhouses"],
  steakhouse:    ["Steakhouses"],
  bbq:           ["Barbeque"],
  barbecue:      ["Barbeque"],
  wings:         ["Chicken Wings"],
  chicken:       ["Chicken Shop", "Chicken Wings"],

  // ── Sandwiches / wraps ────────────────────────────────────────────────────
  sandwich:      ["Sandwiches"],
  sandwiches:    ["Sandwiches"],
  deli:          ["Delicatessen", "Delis"],
  bagel:         ["Bagels"],
  bagels:        ["Bagels"],
  donair:        ["Donairs"],

  // ── Vegetarian / healthy / dietary ───────────────────────────────────────
  vegan:         ["Vegan"],
  vegetarian:    ["Vegetarian"],
  healthy:       ["Vegan", "Vegetarian", "Salad", "Juice Bars & Smoothies"],
  salad:         ["Salad"],
  soup:          ["Soup"],
  acai:          ["Acai Bowls"],
  juice:         ["Juice Bars & Smoothies"],
  smoothie:      ["Juice Bars & Smoothies"],
  glutenfree:    ["Gluten-Free"],
  poke:          ["Poke"],

  // ── Breakfast / brunch ────────────────────────────────────────────────────
  breakfast:     ["Breakfast & Brunch"],
  brunch:        ["Breakfast & Brunch"],
  pancakes:      ["Pancakes"],
  waffle:        ["Waffles"],
  waffles:       ["Waffles"],

  // ── Noodles ───────────────────────────────────────────────────────────────
  noodles:       ["Noodles", "Ramen"],

  // ── Coffee / tea / cafes ─────────────────────────────────────────────────
  coffee:        ["Coffee & Tea", "Cafes"],
  matcha:        ["Coffee & Tea", "Cafes", "Japanese"],
  tea:           ["Coffee & Tea", "Bubble Tea", "Tea Rooms"],
  boba:          ["Bubble Tea"],
  bubble:        ["Bubble Tea"],

  // ── Desserts / sweets ─────────────────────────────────────────────────────
  dessert:       ["Desserts", "Bakeries", "Ice Cream & Frozen Yogurt"],
  desserts:      ["Desserts", "Bakeries"],
  icecream:      ["Ice Cream & Frozen Yogurt"],
  gelato:        ["Gelato"],
  bakery:        ["Bakeries"],
  donut:         ["Donuts"],
  donuts:        ["Donuts"],
  cupcake:       ["Cupcakes"],
  cupcakes:      ["Cupcakes"],
  macaron:       ["Macarons"],
  macarons:      ["Macarons"],
  shavedice:     ["Shaved Ice"],
  chocolate:     ["Chocolatiers & Shops"],

  // ── Bars / nightlife ──────────────────────────────────────────────────────
  bar:           ["Bars", "Cocktail Bars"],
  cocktail:      ["Cocktail Bars"],
  cocktails:     ["Cocktail Bars"],
  wine:          ["Wine Bars", "Wine Tasting Room", "Wineries"],
  beer:          ["Beer Bar", "Beer Gardens", "Beer Hall", "Breweries", "Brewpubs"],
  brewery:       ["Breweries", "Brewpubs"],
  whiskey:       ["Whiskey Bars"],
  champagne:     ["Champagne Bars"],
  speakeasy:     ["Speakeasies"],
  tiki:          ["Tiki Bars"],
  hookah:        ["Hookah Bars"],
  lounge:        ["Lounges"],
  sports:        ["Sports Bars"],
  pub:           ["Gastropubs", "Pubs", "Irish Pub"],
  gastropub:     ["Gastropubs"],
  dive:          ["Dive Bars", "divey"],
  divey:         ["Dive Bars", "divey"],
  nightlife:     ["Bars", "Nightlife"],
  drinks:        ["Bars", "Cocktail Bars"],

  // ── Venue types ───────────────────────────────────────────────────────────
  bistro:        ["Bistros"],
  buffet:        ["Buffets"],
  fast:          ["Fast Food"],
  quick:         ["Fast Food", "Sandwiches"],
  foodtruck:     ["Food Trucks"],

  // ── Ambience / vibe ───────────────────────────────────────────────────────
  cozy:          ["casual", "Cafes", "Coffee & Tea"],
  romantic:      ["romantic", "Italian", "French"],
  casual:        ["casual"],
  trendy:        ["trendy"],
  upscale:       ["upscale", "classy"],
  fancy:         ["upscale", "classy"],
  classy:        ["classy", "upscale"],
  hipster:       ["hipster"],
  intimate:      ["intimate", "romantic"],
  quiet:         ["intimate"],
  touristy:      ["touristy"],
  cheap:         ["casual"],
  affordable:    ["casual"],
  spicy:         ["Thai", "Indian", "Mexican"],
  family:        ["casual"],
  lively:        ["trendy", "Bars"],
};

const keywordLabel: Record<string, string> = {
  cozy: "cozy vibes",
  romantic: "romantic vibes",
  trendy: "trendy vibes",
  fancy: "upscale vibes",
  upscale: "upscale vibes",
  classy: "upscale vibes",
};

const normalize = (value: string): string =>
  value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();

const tagOverlapsAny = (tag: string, candidates: string[]): boolean => {
  const t = normalize(tag);
  return candidates.some((c) => t.includes(normalize(c)) || normalize(c).includes(t));
};

/**
 * Generates a short, user-facing explanation sentence for why a restaurant
 * matches the query. Kept intentionally lightweight (frontend-only).
 */
export function generateMatchExplanation(
  restaurantName: string,
  tags: string[],
  query: string,
  rating: number,
  price: string | undefined,
  score: number,
  ratingThreshold?: number,
): string {
  void restaurantName;
  void rating;
  void price;
  void score;
  void ratingThreshold;

  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const matched: string[] = [];

  for (const word of words) {
    const mapped = keywordMap[word];
    if (!mapped) continue;
    if (tags.some((t) => tagOverlapsAny(t, mapped))) matched.push(word);
  }

  const unique = [...new Set(matched)];
  if (unique.length === 0) {
    const topTags = tags.filter(Boolean).slice(0, 2).join(" and ");
    return topTags ? `Known for ${topTags}.` : "A strong match.";
  }
  if (unique.length === 1) {
    const label = keywordLabel[unique[0]] ?? unique[0];
    return `Matches your search for ${label}.`;
  }

  const labelA = keywordLabel[unique[0]] ?? unique[0];
  const labelB = keywordLabel[unique[1]] ?? unique[1];
  return `Matches your search for ${labelA} and ${labelB}.`;
}

/**
 * Returns subset of a tags that are directly relevant to the
 * query, used to highlight tag pills on the result card.
 */
export function getQueryAwareTags(tags: string[], query: string): string[] {
  if (!query.trim() || tags.length === 0) return [];

  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const relevantCategories = new Set<string>();
  for (const word of words) {
    const mapped = keywordMap[word];
    if (mapped) mapped.forEach((cat) => relevantCategories.add(cat.toLowerCase()));
  }
  if (relevantCategories.size === 0) return [];

  return tags.filter((tag) =>
    [...relevantCategories].some(
      (cat) =>
        tag.toLowerCase().includes(cat) || cat.includes(tag.toLowerCase()),
    ),
  );
}
