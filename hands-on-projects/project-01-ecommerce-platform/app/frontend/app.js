// ===== Config =====
// When running via docker-compose (local/), the API gateway proxies these.
// When running standalone, point to individual service ports.
const API = {
    products: '/api/products',
    cart: '/api/cart',
    orders: '/api/orders',
    payments: '/api/payments',
    inventory: '/api/inventory',
};

const SERVICES = [
    { name: 'Product Service', key: 'product-service', port: 8001, path: '/health' },
    { name: 'Cart Service', key: 'cart-service', port: 8002, path: '/health' },
    { name: 'Order Service', key: 'order-service', port: 8003, path: '/health' },
    { name: 'Payment Service', key: 'payment-service', port: 8004, path: '/health' },
    { name: 'Inventory Service', key: 'inventory-service', port: 8005, path: '/health' },
];

// Simulate a user session
const USER_ID = 'user-' + (localStorage.getItem('shopcloud_user') || (() => {
    const id = Math.random().toString(36).substr(2, 8);
    localStorage.setItem('shopcloud_user', id);
    return id;
})());

let allProducts = [];
let currentCart = { items: [], total: 0, item_count: 0 };


// ===== Init =====

document.addEventListener('DOMContentLoaded', () => {
    // Nav tabs
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', () => switchPage(tab.dataset.page));
    });

    // Cart button
    document.getElementById('cart-btn').addEventListener('click', () => {
        openCart();
        loadCart();
    });

    loadProducts();
    loadCart();
});


// ===== Navigation =====

function switchPage(page) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));

    document.getElementById(`page-${page}`).classList.add('active');
    document.querySelector(`[data-page="${page}"]`).classList.add('active');

    if (page === 'orders') loadOrders();
    if (page === 'inventory') loadInventory();
    if (page === 'services') checkServices();
}


// ===== Products =====

async function loadProducts() {
    const grid = document.getElementById('products-grid');
    grid.innerHTML = '<div class="loading">Loading products...</div>';
    try {
        const [productsRes, categoriesRes] = await Promise.all([
            fetch(API.products),
            fetch(`${API.products}/categories`),
        ]);
        allProducts = await productsRes.json();
        const categories = await categoriesRes.json();

        // Populate category filter
        const select = document.getElementById('category-filter');
        select.innerHTML = '<option value="">All Categories</option>';
        categories.sort().forEach(cat => {
            select.innerHTML += `<option value="${cat}">${cat}</option>`;
        });

        renderProducts(allProducts);
    } catch (e) {
        grid.innerHTML = `<div class="empty-state">Failed to load products. Is the product service running?<br><small>${e.message}</small></div>`;
    }
}

function filterProducts() {
    const search = document.getElementById('search-input').value.toLowerCase();
    const category = document.getElementById('category-filter').value;
    const filtered = allProducts.filter(p =>
        (!category || p.category === category) &&
        (!search || p.name.toLowerCase().includes(search) || (p.description || '').toLowerCase().includes(search))
    );
    renderProducts(filtered);
}

function renderProducts(products) {
    const grid = document.getElementById('products-grid');
    if (!products.length) {
        grid.innerHTML = '<div class="empty-state">No products found.</div>';
        return;
    }
    grid.innerHTML = products.map(p => `
        <div class="product-card">
            <img class="product-img" src="${p.image_url || 'https://picsum.photos/seed/' + p.id + '/400/300'}" alt="${escHtml(p.name)}" loading="lazy">
            <div class="product-body">
                <div class="product-category">${escHtml(p.category)}</div>
                <div class="product-name">${escHtml(p.name)}</div>
                <div class="product-description">${escHtml(p.description || '')}</div>
            </div>
            <div class="product-footer">
                <div class="product-price">$${p.price.toFixed(2)}</div>
                <button class="btn btn-primary btn-sm" onclick="addToCart(${p.id})">Add to Cart</button>
            </div>
        </div>
    `).join('');
}


// ===== Cart =====

async function loadCart() {
    try {
        const res = await fetch(`${API.cart}/${USER_ID}`);
        currentCart = await res.json();
        updateCartUI();
    } catch (e) {
        // Cart service might not be running
    }
}

async function addToCart(productId) {
    try {
        const res = await fetch(`${API.cart}/${USER_ID}/items`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_id: productId, quantity: 1 }),
        });
        if (!res.ok) throw new Error(await res.text());
        currentCart = await res.json();
        updateCartUI();
        toast('Added to cart!', 'success');
    } catch (e) {
        toast('Failed to add item: ' + e.message, 'error');
    }
}

async function removeFromCart(productId) {
    try {
        const res = await fetch(`${API.cart}/${USER_ID}/items/${productId}`, { method: 'DELETE' });
        if (!res.ok) throw new Error(await res.text());
        currentCart = await res.json();
        updateCartUI();
        renderCartDrawer();
    } catch (e) {
        toast('Failed to remove item', 'error');
    }
}

function updateCartUI() {
    const count = currentCart.item_count || 0;
    const badge = document.getElementById('cart-count');
    badge.textContent = count;
    badge.classList.toggle('hidden', count === 0);
}

function renderCartDrawer() {
    const container = document.getElementById('cart-items');
    const footer = document.getElementById('cart-footer');

    if (!currentCart.items || currentCart.items.length === 0) {
        container.innerHTML = '<div class="empty-state">Your cart is empty</div>';
        footer.classList.add('hidden');
        return;
    }

    container.innerHTML = currentCart.items.map(item => `
        <div class="cart-item">
            <img class="cart-item-img" src="${item.image_url || 'https://picsum.photos/seed/' + item.product_id + '/200/200'}" alt="${escHtml(item.name)}">
            <div class="cart-item-info">
                <div class="cart-item-name">${escHtml(item.name)}</div>
                <div class="cart-item-price">$${item.price.toFixed(2)} × <span class="cart-item-qty">${item.quantity}</span></div>
                <div style="font-size:13px;font-weight:600;color:#111">$${item.subtotal.toFixed(2)}</div>
            </div>
            <button class="cart-item-remove" onclick="removeFromCart(${item.product_id})" title="Remove">×</button>
        </div>
    `).join('');

    document.getElementById('cart-total').textContent = `$${currentCart.total.toFixed(2)}`;
    footer.classList.remove('hidden');
}

function openCart() {
    document.getElementById('cart-overlay').classList.add('open');
    document.getElementById('cart-drawer').classList.add('open');
    renderCartDrawer();
}

function closeCart() {
    document.getElementById('cart-overlay').classList.remove('open');
    document.getElementById('cart-drawer').classList.remove('open');
}


// ===== Checkout =====

function showCheckout() {
    closeCart();
    if (!currentCart.items || currentCart.items.length === 0) {
        toast('Your cart is empty', 'error');
        return;
    }
    document.getElementById('summary-items').textContent = currentCart.item_count + ' item(s)';
    document.getElementById('summary-total').textContent = `$${currentCart.total.toFixed(2)}`;
    document.getElementById('order-result').classList.add('hidden');
    document.getElementById('checkout-form').classList.remove('hidden');
    document.getElementById('checkout-overlay').classList.add('open');
    document.getElementById('checkout-modal').classList.add('open');
}

function closeCheckout() {
    document.getElementById('checkout-overlay').classList.remove('open');
    document.getElementById('checkout-modal').classList.remove('open');
}

async function placeOrder(e) {
    e.preventDefault();
    const btn = document.getElementById('place-order-btn');
    btn.disabled = true;
    btn.textContent = 'Processing...';

    const payload = {
        user_id: USER_ID,
        customer_name: document.getElementById('customer-name').value,
        customer_email: document.getElementById('customer-email').value,
        shipping_address: document.getElementById('shipping-address').value,
    };

    const resultEl = document.getElementById('order-result');

    try {
        const res = await fetch(API.orders, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Order failed');
        }

        const order = await res.json();
        currentCart = { items: [], total: 0, item_count: 0 };
        updateCartUI();

        document.getElementById('checkout-form').classList.add('hidden');
        resultEl.className = 'order-result success';
        resultEl.innerHTML = `
            <strong>Order placed successfully!</strong><br>
            Order ID: <strong>#${order.id}</strong><br>
            Payment ID: <code>${order.payment_id}</code><br>
            Total: <strong>$${order.total.toFixed(2)}</strong><br><br>
            <button class="btn btn-secondary btn-sm" onclick="closeCheckout(); switchPage('orders');">View My Orders</button>
        `;
        resultEl.classList.remove('hidden');
        toast('Order placed!', 'success');
    } catch (err) {
        resultEl.className = 'order-result error';
        resultEl.innerHTML = `<strong>Order failed:</strong> ${escHtml(err.message)}`;
        resultEl.classList.remove('hidden');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Place Order';
    }
}


// ===== Orders =====

async function loadOrders() {
    const list = document.getElementById('orders-list');
    list.innerHTML = '<div class="loading">Loading orders...</div>';
    try {
        const res = await fetch(API.orders);
        const orders = await res.json();

        if (!orders.length) {
            list.innerHTML = '<div class="empty-state">No orders yet. Go shopping!</div>';
            return;
        }

        list.innerHTML = orders.map(order => `
            <div class="order-card">
                <div class="order-card-header">
                    <span class="order-id">Order #${order.id}</span>
                    <span class="badge badge-${order.status}">${order.status}</span>
                    <span class="order-date">${new Date(order.created_at).toLocaleString()}</span>
                </div>
                <div class="order-items-summary">
                    ${order.items.length} item(s) — ${order.customer_name || 'Guest'} — ${escHtml(order.shipping_address || '')}
                </div>
                <div class="order-footer">
                    <span class="order-total">$${order.total.toFixed(2)}</span>
                    <span style="font-size:12px;color:#6b7280">Payment: <code>${order.payment_id || 'N/A'}</code></span>
                </div>
            </div>
        `).join('');
    } catch (e) {
        list.innerHTML = `<div class="empty-state">Failed to load orders.<br><small>${e.message}</small></div>`;
    }
}


// ===== Inventory =====

async function loadInventory() {
    const wrap = document.getElementById('inventory-table-wrap');
    wrap.innerHTML = '<div class="loading">Loading inventory...</div>';
    try {
        const res = await fetch(API.inventory);
        const items = await res.json();

        if (!items.length) {
            wrap.innerHTML = '<div class="empty-state">No inventory data.</div>';
            return;
        }

        const rows = items.map(item => {
            const pct = item.quantity > 0 ? Math.min(100, (item.available / item.quantity) * 100) : 0;
            const level = pct < 20 ? 'critical' : pct < 50 ? 'low' : '';
            return `
                <tr>
                    <td>${item.product_id}</td>
                    <td>${escHtml(item.product_name)}</td>
                    <td>${item.quantity}</td>
                    <td>${item.reserved}</td>
                    <td>
                        <div class="stock-bar-wrap">
                            <div class="stock-bar"><div class="stock-bar-fill ${level}" style="width:${pct}%"></div></div>
                            <span>${item.available}</span>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        wrap.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>ID</th><th>Product</th><th>Total</th><th>Reserved</th><th>Available</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        `;
    } catch (e) {
        wrap.innerHTML = `<div class="empty-state">Failed to load inventory.<br><small>${e.message}</small></div>`;
    }
}


// ===== Services Health =====

async function checkServices() {
    const grid = document.getElementById('services-grid');
    grid.innerHTML = SERVICES.map(s => `
        <div class="service-card" id="svc-${s.key}">
            <div>
                <div class="service-name">${s.name}</div>
                <div class="service-port">:${s.port}</div>
            </div>
            <div class="service-status">
                <span class="status-dot checking"></span>
                <span>Checking...</span>
            </div>
        </div>
    `).join('');

    SERVICES.forEach(async (s) => {
        const card = document.getElementById(`svc-${s.key}`);
        const statusEl = card.querySelector('.service-status');
        try {
            const res = await fetch(`/api/${s.key}${s.path}`, { signal: AbortSignal.timeout(3000) });
            const healthy = res.ok;
            statusEl.innerHTML = `
                <span class="status-dot ${healthy ? 'healthy' : 'down'}"></span>
                <span>${healthy ? 'Healthy' : 'Unhealthy'}</span>
            `;
        } catch {
            statusEl.innerHTML = `<span class="status-dot down"></span><span>Unreachable</span>`;
        }
    });
}


// ===== Helpers =====

function escHtml(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

let toastTimer;
function toast(msg, type = '') {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = `toast ${type}`;
    el.classList.remove('hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.add('hidden'), 3000);
}
