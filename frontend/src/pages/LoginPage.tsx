import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, GraduationCap, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";
import { useAuth } from "@/auth/useAuth";
import { LoadingState } from "@/components/LoadingState";
import { ApiError } from "@/services/api-client";

const loginSchema = z.object({
  identifier: z.string().trim().min(1, "Enter your username or email."),
  password: z.string().min(1, "Enter your password."),
  school_code: z.string().trim().optional(),
});

type LoginValues = z.infer<typeof loginSchema>;

export function LoginPage() {
  const { login, status } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const locationState = location.state as {
    from?: { pathname?: string };
    logoutError?: string;
  } | null;
  const [showPassword, setShowPassword] = useState(false);
  const [submitError, setSubmitError] = useState(
    locationState?.logoutError ?? "",
  );
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { identifier: "", password: "", school_code: "" },
  });

  if (status === "restoring")
    return <LoadingState label="Restoring your secure session…" />;
  if (status === "authenticated") return <Navigate to="/" replace />;

  const submit = async (values: LoginValues) => {
    setSubmitError("");
    try {
      await login({
        identifier: values.identifier,
        password: values.password,
        ...(values.school_code ? { school_code: values.school_code } : {}),
      });
      const destination = locationState?.from?.pathname ?? "/";
      navigate(destination, { replace: true });
    } catch (error) {
      setSubmitError(
        error instanceof ApiError && error.status === 429
          ? "Too many attempts. Please wait a few minutes and try again."
          : "We couldn't sign you in with those details. Check them and try again.",
      );
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="login-title">
        <div className="auth-brand">
          <span className="brand-mark">
            <GraduationCap aria-hidden="true" size={25} />
          </span>
          <span>
            <strong>Smart School</strong>
            <small>Learning &amp; Assessment</small>
          </span>
        </div>
        <div className="auth-heading">
          <div className="auth-eyebrow">
            <ShieldCheck aria-hidden="true" size={15} />
            Secure school access
          </div>
          <h1 id="login-title">Welcome back</h1>
          <p>Sign in with the account provided by your school administrator.</p>
        </div>

        <form className="auth-form" onSubmit={handleSubmit(submit)} noValidate>
          <label htmlFor="identifier">Username or email</label>
          <input
            id="identifier"
            autoComplete="username"
            autoFocus
            {...register("identifier")}
            aria-invalid={Boolean(errors.identifier)}
            aria-describedby={
              errors.identifier ? "identifier-error" : undefined
            }
          />
          {errors.identifier && (
            <span className="field-error" id="identifier-error">
              {errors.identifier.message}
            </span>
          )}

          <label htmlFor="school-code">
            School code <span>(optional)</span>
          </label>
          <input
            id="school-code"
            autoComplete="organization"
            {...register("school_code")}
          />

          <label htmlFor="password">Password</label>
          <div className="password-field">
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              {...register("password")}
              aria-invalid={Boolean(errors.password)}
              aria-describedby={errors.password ? "password-error" : undefined}
            />
            <button
              type="button"
              className="password-toggle"
              aria-label={showPassword ? "Hide password" : "Show password"}
              onClick={() => setShowPassword((visible) => !visible)}
            >
              {showPassword ? (
                <EyeOff aria-hidden="true" size={18} />
              ) : (
                <Eye aria-hidden="true" size={18} />
              )}
            </button>
          </div>
          {errors.password && (
            <span className="field-error" id="password-error">
              {errors.password.message}
            </span>
          )}

          {submitError && (
            <div className="auth-error" role="alert">
              {submitError}
            </div>
          )}
          <button className="auth-submit" type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="auth-footnote">
          Accounts are created by your school. Public registration is disabled.
        </p>
      </section>
    </main>
  );
}
