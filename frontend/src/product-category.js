export function categoryDetails(category) {
  const name = String(category || '').trim().toLowerCase()
  const profiles = {
    fish: ['Mackerel', ['Kg', 'Nos', 'Pack'], 'Choose weight, individual pieces or separately stocked prepared packs.'],
    seafood: ['Prawns or crabs', ['Kg', 'Nos', 'Pack'], 'Choose weight, individual pieces or separately stocked prepared packs.'],
    rice: ['Raw rice', ['Kg', 'Pack'], 'Loose rice: choose Kg, then add weight options such as 500 g and 1 kg. Bagged rice: use Pack with the bag size in the name.'],
    vegetables: ['Tomatoes', ['Kg', 'Nos', 'Bunch', 'Pack'], 'Use Kg for weighed vegetables, Nos for individual vegetables, or Bunch for leafy greens.'],
    fruits: ['Bananas or apples', ['Kg', 'Nos', 'Dozen', 'Pack'], 'Choose how stock is received and sold. Dozen counts whole dozens; it does not automatically share loose-piece stock.'],
    'dairy & eggs': ['Eggs or milk', ['Nos', 'Litre', 'Pack', 'Bottle', 'Kg'], 'Eggs: choose Nos and add 6-piece or 12-piece packs sharing piece stock. Milk: choose Litre or Bottle.'],
    'fast food': ['Chicken fried rice — Half Plate', ['Plate', 'Bowl', 'Nos', 'Pack'], 'Use Plate for both full and half portions, with the portion size in separate product names. Each product has its own price and stock.'],
    bakery: ['Bread or cake', ['Nos', 'Pack', 'Box', 'Kg'], 'Choose pieces for individual items or Pack/Box for separately stocked packages.'],
    snacks: ['Samosa', ['Nos', 'Plate', 'Pack', 'Kg'], 'Use Nos for individual snacks, Plate for portions or Pack for packaged snacks.'],
    beverages: ['Juice', ['Glass', 'Cup', 'Bottle', 'Litre'], 'Choose Glass or Cup for servings, Bottle for bottled drinks or Litre for measured stock.'],
    'meat & poultry': ['Chicken', ['Kg', 'Nos', 'Pack'], 'Choose Kg for weighed meat or separate pieces and packs.'],
  }
  const [example, units, help] = profiles[name] || ['Product name', [], 'Choose the unit used to receive stock and price this product.']
  return { example, units, help }
}
