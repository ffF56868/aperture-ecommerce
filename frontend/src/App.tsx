import { Route, Routes } from "react-router-dom";
import { MainLayout } from "@/layouts/MainLayout";
import { Home } from "@/pages/Home";
import { Shop } from "@/pages/Shop";
import { CategoryRedirect } from "@/pages/CategoryRedirect";
import { ProductDetail } from "@/pages/ProductDetail";
import { CartPage } from "@/pages/CartPage";
import { Checkout } from "@/pages/Checkout";
import { Login } from "@/pages/auth/Login";
import { Register } from "@/pages/auth/Register";
import { VerifyOtp } from "@/pages/auth/VerifyOtp";
import { Profile } from "@/pages/profile/Profile";
import { About } from "@/pages/About";
import { Contact } from "@/pages/Contact";
import { AfterSalesAgent } from "@/pages/AfterSalesAgent";
import { StaffAfterSalesWorkbench } from "@/pages/StaffAfterSalesWorkbench";
import { Notifications } from "@/pages/Notifications";
import { NotFound } from "@/pages/NotFound";

export function App() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route path="/" element={<Home />} />
        <Route path="/products" element={<Shop />} />
        <Route path="/category/:slug" element={<CategoryRedirect />} />
        <Route path="/product/:slug" element={<ProductDetail />} />
        <Route path="/cart" element={<CartPage />} />
        <Route path="/checkout" element={<Checkout />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/verify-otp" element={<VerifyOtp />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/about" element={<About />} />
        <Route path="/contact" element={<Contact />} />
        <Route path="/after-sales" element={<AfterSalesAgent />} />
        <Route path="/notifications" element={<Notifications />} />
        <Route path="/staff/after-sales" element={<StaffAfterSalesWorkbench />} />
        <Route path="/404" element={<NotFound />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
