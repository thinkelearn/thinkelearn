const checkoutForms = document.querySelectorAll("[data-checkout-form]");

const getCookie = (name) => {
    if (!document.cookie) {
        return null;
    }
    const csrfCookies = document.cookie
        .split(";")
        .map((cookie) => cookie.trim())
        .filter((cookie) => cookie.startsWith(`${name}=`));
    if (!csrfCookies.length) {
        return null;
    }
    return decodeURIComponent(csrfCookies[0].split("=")[1]);
};

const appendSessionPlaceholder = (url) => {
    if (!url) {
        return url;
    }
    const connector = url.includes("?") ? "&" : "?";
    return `${url}${connector}session_id={CHECKOUT_SESSION_ID}`;
};

const appendQuery = (url, key, value) => {
    if (!url) {
        return url;
    }
    const connector = url.includes("?") ? "&" : "?";
    return `${url}${connector}${encodeURIComponent(key)}=${encodeURIComponent(value)}`;
};

checkoutForms.forEach((form) => {
    const button = form.querySelector("[data-checkout-submit]");
    const buttonText = form.querySelector("[data-checkout-button-text]");
    const errorElement = form.querySelector("[data-checkout-error]");
    const amountInput = form.querySelector("[data-checkout-amount]");
    const suggestedButton = form.querySelector("[data-checkout-suggested]");
    const pricingType = form.dataset.pricingType;

    const setError = (message) => {
        if (!errorElement) {
            return;
        }
        errorElement.textContent = message;
        errorElement.classList.remove("hidden");
    };

    const clearError = () => {
        if (!errorElement) {
            return;
        }
        errorElement.textContent = "";
        errorElement.classList.add("hidden");
    };

    if (suggestedButton && amountInput) {
        suggestedButton.addEventListener("click", () => {
            amountInput.value = suggestedButton.dataset.suggestedAmount || "";
        });
    }

    if (!button) {
        return;
    }

    button.addEventListener("click", async () => {
        clearError();

        const originalText = buttonText ? buttonText.textContent : "";
        button.disabled = true;
        button.classList.add("opacity-70", "cursor-not-allowed");
        if (buttonText) {
            buttonText.textContent = "Processing...";
        }

        const payload = {
            product_id: form.dataset.productId,
            success_url: appendSessionPlaceholder(form.dataset.successUrl),
            cancel_url: form.dataset.cancelUrl,
        };

        if (amountInput) {
            const amountValue = amountInput.value;
            const minPrice = parseFloat(form.dataset.minPrice || "0");
            const maxPrice = parseFloat(form.dataset.maxPrice || "0");
            const parsedAmount = parseFloat(amountValue);

            if (!amountValue || Number.isNaN(parsedAmount)) {
                setError("Please enter a valid amount to continue.");
                button.disabled = false;
                button.classList.remove("opacity-70", "cursor-not-allowed");
                if (buttonText) {
                    buttonText.textContent = originalText;
                }
                return;
            }

            if (parsedAmount < minPrice || parsedAmount > maxPrice) {
                setError(
                    `Please enter an amount between $${minPrice.toFixed(
                        2
                    )} and $${maxPrice.toFixed(2)}.`
                );
                button.disabled = false;
                button.classList.remove("opacity-70", "cursor-not-allowed");
                if (buttonText) {
                    buttonText.textContent = originalText;
                }
                return;
            }

            payload.amount = parsedAmount;
        }

        try {
            const response = await fetch(form.dataset.checkoutUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken"),
                },
                body: JSON.stringify(payload),
            });

            const data = await response.json();

            if (!response.ok) {
                setError(data.error || "Payment could not be started. Please try again.");
                return;
            }

            if (data.status === "free") {
                const successUrl = appendQuery(
                    form.dataset.successUrl,
                    "free",
                    "1"
                );
                window.location.assign(successUrl);
                return;
            }

            if (data.session_url) {
                window.location.assign(data.session_url);
                return;
            }

            if (pricingType === "free") {
                window.location.assign(form.dataset.successUrl);
                return;
            }

            setError("Unable to continue to checkout. Please try again.");
        } catch (error) {
            setError("Network error. Please refresh the page and try again.");
        } finally {
            button.disabled = false;
            button.classList.remove("opacity-70", "cursor-not-allowed");
            if (buttonText) {
                buttonText.textContent = originalText;
            }
        }
    });
});
