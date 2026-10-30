// Category labels describe the product; they do not prove stock, freshness or offers.
const themes = [
  [/fish|seafood|prawn|crab|shellfish/i, [
    ['Fish on the menu? 🐟', 'Plan a fish curry or a pan-fried favourite'],
    ['Curry or fry? You decide 🍽️', 'Find inspiration for your next seafood meal'],
    ['A seafood idea for dinner 🐟', 'Bring a seafood recipe to your meal plan'],
    ['Make it a fish-meal day 🍲', 'Thinking about your next fish dish'],
    ['Your next seafood recipe starts here 🐟', 'Planning something from the sea for your table'],
  ]],
  [/dairy|egg|milk|cheese/i, [
    ['Breakfast plans? Start here 🍳', 'Find an idea for your breakfast basket'],
    ['A little inspiration for your kitchen 🥣', 'Plan your next kitchen top-up'],
    ['Something for your morning menu ☀️', 'Get your shopping list ready for breakfast'],
    ['Check your fridge list 📝', 'Planning your next fridge restock'],
    ['Your next recipe needs a look 🍽️', 'Browse an option for your next homemade meal'],
  ]],
  [/vegetable|fruit|produce/i, [
    ['Add colour to your meal plan 🥕', 'Find inspiration for your next plate'],
    ['What’s in your produce basket? 🧺', 'Plan your fruit and vegetable shopping'],
    ['A colourful idea for your kitchen 🌈', 'Explore an option for your next recipe'],
    ['Time to plan your produce shop 📝', 'Make a little room on your produce list'],
    ['Your next meal starts with an idea 🍽️', 'Find something to inspire your kitchen plans'],
  ]],
  [/meat|chicken|poultry|mutton/i, [
    ['What’s cooking next? 🍲', 'Find an idea for your next home-cooked meal'],
    ['Dinner plans taking shape? 🍽️', 'Explore an option for your dinner menu'],
    ['Bring a new recipe to the table 🧑‍🍳', 'Start planning your next kitchen creation'],
    ['A meal idea worth a look 🍲', 'Find inspiration for your next family meal'],
    ['Your next cooking plan starts here 📝', 'Build your shopping list around your next recipe'],
  ]],
  [/bakery|bread|cake|dessert|sweet|snack|biscuit/i, [
    ['Something for your break? ☕', 'Explore an idea for your next break'],
    ['Make room on your snack list 📝', 'Find inspiration for your snack cupboard'],
    ['A little treat to explore ✨', 'Browse something for your next treat-time plan'],
    ['Planning a tea-time break? 🫖', 'Take a look while planning your tea-time basket'],
    ['Your next snack idea is here 🧺', 'Discover an option for your next snack shop'],
  ]],
  [/beverage|drink|juice|coffee|tea/i, [
    ['What’s in your cup next? ☕', 'Find inspiration for your next drinks order'],
    ['Take a sip of inspiration 🥤', 'Explore an option for your drinks list'],
    ['Planning your next break? 🫖', 'Browse something for your next drinks break'],
    ['Check your drinks shelf 📝', 'Plan your next beverage top-up'],
    ['A drink idea worth exploring ✨', 'Discover an option for your next drinks basket'],
  ]],
  [/food|grocery|groceries|rice|grain|pulse|spice|pantry|staple|oil/i, [
    ['What’s cooking in your kitchen? 🍲', 'Find inspiration for your next meal'],
    ['Check your pantry list 📝', 'Plan your next pantry top-up'],
    ['Your next recipe starts here 🧑‍🍳', 'Explore an option for your cooking plans'],
    ['Make room in your meal plan 🍽️', 'Build your basket for your next homemade meal'],
    ['A kitchen idea worth exploring 🧺', 'Discover something for your next grocery shop'],
  ]],
]
const general = [
  ['What’s on your list? 🛍️', 'Find inspiration for your next basket'],
  ['Your next local find awaits ✨', 'Explore an idea for your next shopping trip'],
  ['A little shopping inspiration 💡', 'Take a look while planning your next order'],
  ['Make room on your shopping list 📝', 'Discover an option for your next basket'],
  ['Shopping plans? Start here 🧺', 'Explore something for your next local shop'],
]
export function campaignSuggestions(product, shop) {
  const theme = product ? themes.find(([pattern]) => pattern.test(product.item_group || ''))?.[1] || general : general
  const name = String(product?.item_name || '').trim()
  const store = String(shop || '').trim()
  return theme.map(([title, lead]) => {
    const detail = name ? `Explore ${name} at ${store}.` : `Browse ${store}.`
    const message = `${lead}. ${detail} Tap for current prices and availability.`
    return {
      title,
      message: message.length <= 240 ? message : `${lead}. Tap to explore the selected ${name ? 'product' : 'shop'} and check current prices and availability.`,
    }
  })
}
