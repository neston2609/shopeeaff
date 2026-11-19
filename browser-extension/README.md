# Shopee Aff Product Import

1. Extract this ZIP to a permanent folder.
2. In the Chrome profile where you use Shopee, open `chrome://extensions`.
3. Enable Developer mode, choose **Load unpacked**, and select the extracted folder containing `manifest.json`.
4. Open the real Shopee product page, sign in yourself if required, and wait for its details to appear. Expand the description if needed.
5. Open **Shopee Product Import** from the Chrome extensions menu. Select **Read This Product**, review the result, then **Copy Product Data** or **Download JSON**.
6. In Studio, keep your original affiliate shortlink, select **Fetch Information**, then use **Import from Chrome** to paste or upload the exported JSON. Review the matched product before applying it and save normally.

This extension uses only temporary `activeTab` and `scripting` permissions. It has no host permissions, background task, cookies permission, history permission or network access. It does not read login fields, passwords, cookies or browser storage. It does not sign in, solve verification challenges, select variants, purchase anything, or change the Shopee page. Product images are not imported. Prices absent from the product markup remain blank; coupon and related-product prices are not used.

The app checks the exported product IDs against the resolved shortlink before applying fields. Your viewer/affiliate shortlink, including all query parameters, is never replaced by the source product URL. This tool copies the product information the site displays; it does not independently verify seller claims.
