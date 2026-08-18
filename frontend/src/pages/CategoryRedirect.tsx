import { Navigate, useParams } from "react-router-dom";

export function CategoryRedirect() {
  const { slug } = useParams<{ slug: string }>();
  return <Navigate to={`/products?category=${slug}`} replace />;
}
