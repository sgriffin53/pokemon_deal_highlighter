const listings = document.querySelectorAll('.s-item');
const payload = [];

listings.forEach(item => {
  const titleEl = item.querySelector('.s-item__title');
  const linkEl = item.querySelector('.s-item__link');
  const priceEl = item.querySelector('.s-item__price');

  if (titleEl && linkEl && priceEl) {
    payload.push({
      title: titleEl.textContent.trim(),
      url: linkEl.href,
      price: priceEl.textContent.trim()
    });
  }
});

// Send to backend and inject banners on response
fetch('http://localhost:5000/get_values', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ listings: payload })
})
  .then(response => response.json())
  .then(data => {
    console.log('Valuation response:', data);

    // Inject banners into listings using the response
    data.forEach((valuationData, i) => {
      const listing = Array.from(listings).find(l => {
        const link = l.querySelector('.s-item__link');
        return link && link.href === valuationData.url;
      });

      if (!listing) return;

      const wrapper = document.createElement('div');
      wrapper.className = 'poke-wrapper';
      wrapper.style.position = 'absolute';
      wrapper.style.top = '5px';
      wrapper.style.left = '5px';
      wrapper.style.zIndex = '1000';

      const isOver = valuationData.percent > 0;
      const banner = document.createElement('div');
      banner.className = `poke-price-banner ${isOver ? 'over' : 'under'}`;
      banner.innerText = valuationData.banner_text;
      banner.style.cursor = 'pointer';

      const panel = document.createElement('div');
      panel.className = 'poke-info-panel';
      panel.style.display = 'none';
      panel.innerHTML = `
        <strong>Identified as:</strong> ${valuationData.identified_set} ${valuationData.identified_card}<br>
        <strong>Price:</strong> $${valuationData.price.toFixed(2)}<br>
        <strong>Valuation:</strong> $${valuationData.valuation.toFixed(2)}<br>
        <a href="${valuationData.pricecharting_url}" target="_blank">Pricecharting Page</a><br>
        <a href="${valuationData.modified_url}" target="_blank">View on eBay</a>
      `;

      banner.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        panel.style.display = panel.style.display === 'block' ? 'none' : 'block';
      });

      wrapper.appendChild(banner);
      wrapper.appendChild(panel);
      listing.style.position = 'relative';
      listing.appendChild(wrapper);
    });
  })
  .catch(error => {
    console.error('Error sending listings to backend:', error);
  });