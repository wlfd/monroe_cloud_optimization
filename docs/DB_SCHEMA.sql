--
-- PostgreSQL database dump
--

-- Dumped from database version 15.16 (Debian 15.16-1.pgdg13+1)
-- Dumped by pg_dump version 15.16 (Debian 15.16-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: cloudcost
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO cloudcost;

--
-- Name: alert_events; Type: TABLE; Schema: public; Owner: cloudcost
--

CREATE TABLE public.alert_events (
    id uuid NOT NULL,
    budget_id uuid NOT NULL,
    threshold_id uuid,
    triggered_at timestamp with time zone NOT NULL,
    billing_period character varying(7) NOT NULL,
    spend_at_trigger numeric(18,2) NOT NULL,
    budget_amount numeric(18,2) NOT NULL,
    threshold_percent integer NOT NULL,
    delivery_status character varying(20) DEFAULT 'pending'::character varying NOT NULL
);


ALTER TABLE public.alert_events OWNER TO cloudcost;

--
-- Name: allocation_rules; Type: TABLE; Schema: public; Owner: cloudcost
--

CREATE TABLE public.allocation_rules (
    id uuid NOT NULL,
    priority integer NOT NULL,
    target_type character varying(50) NOT NULL,
    target_value character varying(255) NOT NULL,
    method character varying(50) NOT NULL,
    manual_pct json,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


ALTER TABLE public.allocation_rules OWNER TO cloudcost;

--
-- Name: anomalies; Type: TABLE; Schema: public; Owner: cloudcost
--

CREATE TABLE public.anomalies (
    id uuid NOT NULL,
    detected_date date NOT NULL,
    service_name character varying(255) NOT NULL,
    resource_group character varying(255) NOT NULL,
    description text NOT NULL,
    severity character varying(50) NOT NULL,
    status character varying(50) NOT NULL,
    expected boolean NOT NULL,
    baseline_daily_avg numeric(18,6) NOT NULL,
    current_daily_cost numeric(18,6) NOT NULL,
    pct_deviation numeric(10,2) NOT NULL,
    estimated_monthly_impact numeric(18,2) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


ALTER TABLE public.anomalies OWNER TO cloudcost;

--
-- Name: billing_records; Type: TABLE; Schema: public; Owner: cloudcost
--

CREATE TABLE public.billing_records (
    id uuid NOT NULL,
    usage_date date NOT NULL,
    subscription_id character varying(255) NOT NULL,
    resource_group character varying(255) NOT NULL,
    service_name character varying(255) NOT NULL,
    meter_category character varying(255) NOT NULL,
    pre_tax_cost numeric(18,6) NOT NULL,
    currency character varying(10) NOT NULL,
    ingested_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    region character varying(100) DEFAULT ''::character varying NOT NULL,
    tag character varying(500) DEFAULT ''::character varying NOT NULL,
    resource_id character varying(500) DEFAULT ''::character varying NOT NULL,
    resource_name character varying(500) DEFAULT ''::character varying NOT NULL
);


ALTER TABLE public.billing_records OWNER TO cloudcost;

--
-- Name: budget_thresholds; Type: TABLE; Schema: public; Owner: cloudcost
--

CREATE TABLE public.budget_thresholds (
    id uuid NOT NULL,
    budget_id uuid NOT NULL,
    threshold_percent integer NOT NULL,
    notification_channel_id uuid,
    last_triggered_at timestamp with time zone,
    last_triggered_period character varying(7)
);


ALTER TABLE public.budget_thresholds OWNER TO cloudcost;

--
-- Name: budgets; Type: TABLE; Schema: public; Owner: cloudcost
--

CREATE TABLE public.budgets (
    id uuid NOT NULL,
    name character varying(255) NOT NULL,
    scope_type character varying(50) NOT NULL,
    scope_value character varying(500),
    amount_usd numeric(18,2) NOT NULL,
    period character varying(20) DEFAULT 'monthly'::character varying NOT NULL,
    start_date date NOT NULL,
    end_date date,
    is_active boolean DEFAULT true NOT NULL,
    created_by uuid,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


ALTER TABLE public.budgets OWNER TO cloudcost;

--
-- Name: ingestion_alerts; Type: TABLE; Schema: public; Owner: cloudcost
--

CREATE TABLE public.ingestion_alerts (
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    error_message text NOT NULL,
    retry_count integer NOT NULL,
    failed_at timestamp with time zone NOT NULL,
    is_active boolean NOT NULL,
    cleared_at timestamp with time zone,
    cleared_by character varying(50)
);


ALTER TABLE public.ingestion_alerts OWNER TO cloudcost;

--
-- Name: ingestion_runs; Type: TABLE; Schema: public; Owner: cloudcost
--

CREATE TABLE public.ingestion_runs (
    id uuid NOT NULL,
    started_at timestamp with time zone NOT NULL,
    completed_at timestamp with time zone,
    status character varying(50) NOT NULL,
    triggered_by character varying(50) NOT NULL,
    records_ingested integer NOT NULL,
    window_start timestamp with time zone,
    window_end timestamp with time zone,
    retry_count integer NOT NULL,
    error_detail text
);


ALTER TABLE public.ingestion_runs OWNER TO cloudcost;

--
-- Name: notification_channels; Type: TABLE; Schema: public; Owner: cloudcost
--

CREATE TABLE public.notification_channels (
    id uuid NOT NULL,
    name character varying(255) NOT NULL,
    channel_type character varying(20) NOT NULL,
    config_json jsonb NOT NULL,
    owner_user_id uuid,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.notification_channels OWNER TO cloudcost;

--
-- Name: notification_deliveries; Type: TABLE; Schema: public; Owner: cloudcost
--

CREATE TABLE public.notification_deliveries (
    id uuid NOT NULL,
    channel_id uuid NOT NULL,
    event_type character varying(100) NOT NULL,
    event_id uuid NOT NULL,
    payload_json jsonb,
    attempt_number integer DEFAULT 1 NOT NULL,
    attempted_at timestamp with time zone NOT NULL,
    status character varying(20) NOT NULL,
    response_code integer,
    error_message text
);


ALTER TABLE public.notification_deliveries OWNER TO cloudcost;

--
-- Name: recommendations; Type: TABLE; Schema: public; Owner: cloudcost
--

CREATE TABLE public.recommendations (
    id uuid NOT NULL,
    generated_date date NOT NULL,
    resource_name character varying(500) NOT NULL,
    resource_group character varying(255) NOT NULL,
    subscription_id character varying(255) NOT NULL,
    service_name character varying(255) NOT NULL,
    meter_category character varying(255) NOT NULL,
    category character varying(50) NOT NULL,
    explanation character varying(2000) NOT NULL,
    estimated_monthly_savings numeric(18,2) NOT NULL,
    confidence_score integer NOT NULL,
    current_monthly_cost numeric(18,2) NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.recommendations OWNER TO cloudcost;

--
-- Name: tenant_attributions; Type: TABLE; Schema: public; Owner: cloudcost
--

CREATE TABLE public.tenant_attributions (
    id uuid NOT NULL,
    tenant_id character varying(255) NOT NULL,
    year integer NOT NULL,
    month integer NOT NULL,
    total_cost numeric(18,6) NOT NULL,
    pct_of_total numeric(10,4) NOT NULL,
    mom_delta_usd numeric(18,6),
    top_service_category character varying(255),
    allocated_cost numeric(18,6) NOT NULL,
    tagged_cost numeric(18,6) NOT NULL,
    computed_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


ALTER TABLE public.tenant_attributions OWNER TO cloudcost;

--
-- Name: tenant_profiles; Type: TABLE; Schema: public; Owner: cloudcost
--

CREATE TABLE public.tenant_profiles (
    id uuid NOT NULL,
    tenant_id character varying(255) NOT NULL,
    display_name character varying(255),
    is_new boolean DEFAULT true NOT NULL,
    acknowledged_at timestamp with time zone,
    first_seen date NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


ALTER TABLE public.tenant_profiles OWNER TO cloudcost;

--
-- Name: user_sessions; Type: TABLE; Schema: public; Owner: cloudcost
--

CREATE TABLE public.user_sessions (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    token_hash character varying(255) NOT NULL,
    ip_address inet,
    user_agent text,
    created_at timestamp with time zone NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked boolean NOT NULL,
    revoked_at timestamp with time zone
);


ALTER TABLE public.user_sessions OWNER TO cloudcost;

--
-- Name: users; Type: TABLE; Schema: public; Owner: cloudcost
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    full_name character varying(255),
    role character varying(50) NOT NULL,
    is_active boolean NOT NULL,
    failed_login_attempts integer NOT NULL,
    locked_until timestamp with time zone,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    last_login timestamp with time zone
);


ALTER TABLE public.users OWNER TO cloudcost;

--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: alert_events alert_events_pkey; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.alert_events
    ADD CONSTRAINT alert_events_pkey PRIMARY KEY (id);


--
-- Name: allocation_rules allocation_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.allocation_rules
    ADD CONSTRAINT allocation_rules_pkey PRIMARY KEY (id);


--
-- Name: anomalies anomalies_pkey; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.anomalies
    ADD CONSTRAINT anomalies_pkey PRIMARY KEY (id);


--
-- Name: billing_records billing_records_pkey; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.billing_records
    ADD CONSTRAINT billing_records_pkey PRIMARY KEY (id);


--
-- Name: budget_thresholds budget_thresholds_pkey; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.budget_thresholds
    ADD CONSTRAINT budget_thresholds_pkey PRIMARY KEY (id);


--
-- Name: budgets budgets_pkey; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.budgets
    ADD CONSTRAINT budgets_pkey PRIMARY KEY (id);


--
-- Name: ingestion_alerts ingestion_alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.ingestion_alerts
    ADD CONSTRAINT ingestion_alerts_pkey PRIMARY KEY (id);


--
-- Name: ingestion_runs ingestion_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.ingestion_runs
    ADD CONSTRAINT ingestion_runs_pkey PRIMARY KEY (id);


--
-- Name: notification_channels notification_channels_pkey; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.notification_channels
    ADD CONSTRAINT notification_channels_pkey PRIMARY KEY (id);


--
-- Name: notification_deliveries notification_deliveries_pkey; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.notification_deliveries
    ADD CONSTRAINT notification_deliveries_pkey PRIMARY KEY (id);


--
-- Name: recommendations recommendations_pkey; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.recommendations
    ADD CONSTRAINT recommendations_pkey PRIMARY KEY (id);


--
-- Name: tenant_attributions tenant_attributions_pkey; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.tenant_attributions
    ADD CONSTRAINT tenant_attributions_pkey PRIMARY KEY (id);


--
-- Name: tenant_profiles tenant_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.tenant_profiles
    ADD CONSTRAINT tenant_profiles_pkey PRIMARY KEY (id);


--
-- Name: tenant_profiles tenant_profiles_tenant_id_key; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.tenant_profiles
    ADD CONSTRAINT tenant_profiles_tenant_id_key UNIQUE (tenant_id);


--
-- Name: allocation_rules uq_allocation_rule_priority; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.allocation_rules
    ADD CONSTRAINT uq_allocation_rule_priority UNIQUE (priority);


--
-- Name: anomalies uq_anomaly_key; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.anomalies
    ADD CONSTRAINT uq_anomaly_key UNIQUE (service_name, resource_group, detected_date);


--
-- Name: billing_records uq_billing_record_key; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.billing_records
    ADD CONSTRAINT uq_billing_record_key UNIQUE (usage_date, subscription_id, resource_group, service_name, meter_category);


--
-- Name: tenant_attributions uq_tenant_attribution_key; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.tenant_attributions
    ADD CONSTRAINT uq_tenant_attribution_key UNIQUE (tenant_id, year, month);


--
-- Name: user_sessions user_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_pkey PRIMARY KEY (id);


--
-- Name: user_sessions user_sessions_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_token_hash_key UNIQUE (token_hash);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: idx_alert_events_budget_id; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_alert_events_budget_id ON public.alert_events USING btree (budget_id);


--
-- Name: idx_alert_events_triggered_at; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_alert_events_triggered_at ON public.alert_events USING btree (triggered_at);


--
-- Name: idx_anomaly_detected_date; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_anomaly_detected_date ON public.anomalies USING btree (detected_date);


--
-- Name: idx_anomaly_severity; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_anomaly_severity ON public.anomalies USING btree (severity);


--
-- Name: idx_anomaly_status; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_anomaly_status ON public.anomalies USING btree (status);


--
-- Name: idx_attribution_tenant_id; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_attribution_tenant_id ON public.tenant_attributions USING btree (tenant_id);


--
-- Name: idx_attribution_year_month; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_attribution_year_month ON public.tenant_attributions USING btree (year, month);


--
-- Name: idx_billing_region; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_billing_region ON public.billing_records USING btree (region);


--
-- Name: idx_billing_resource_group; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_billing_resource_group ON public.billing_records USING btree (resource_group);


--
-- Name: idx_billing_service_name; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_billing_service_name ON public.billing_records USING btree (service_name);


--
-- Name: idx_billing_subscription; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_billing_subscription ON public.billing_records USING btree (subscription_id);


--
-- Name: idx_billing_usage_date; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_billing_usage_date ON public.billing_records USING btree (usage_date);


--
-- Name: idx_budget_thresholds_budget_id; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_budget_thresholds_budget_id ON public.budget_thresholds USING btree (budget_id);


--
-- Name: idx_budgets_active; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_budgets_active ON public.budgets USING btree (is_active);


--
-- Name: idx_ingestion_alerts_active; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_ingestion_alerts_active ON public.ingestion_alerts USING btree (is_active);


--
-- Name: idx_ingestion_runs_started_at; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_ingestion_runs_started_at ON public.ingestion_runs USING btree (started_at);


--
-- Name: idx_notification_channels_active; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_notification_channels_active ON public.notification_channels USING btree (is_active);


--
-- Name: idx_notification_deliveries_event; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_notification_deliveries_event ON public.notification_deliveries USING btree (event_type, event_id);


--
-- Name: idx_notification_deliveries_failed; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_notification_deliveries_failed ON public.notification_deliveries USING btree (status, attempt_number);


--
-- Name: idx_recommendation_category; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_recommendation_category ON public.recommendations USING btree (category);


--
-- Name: idx_recommendation_generated_date; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_recommendation_generated_date ON public.recommendations USING btree (generated_date);


--
-- Name: idx_recommendation_resource; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_recommendation_resource ON public.recommendations USING btree (resource_name, resource_group);


--
-- Name: idx_user_sessions_token_hash; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_user_sessions_token_hash ON public.user_sessions USING btree (token_hash);


--
-- Name: idx_user_sessions_user_id; Type: INDEX; Schema: public; Owner: cloudcost
--

CREATE INDEX idx_user_sessions_user_id ON public.user_sessions USING btree (user_id);


--
-- Name: alert_events alert_events_budget_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.alert_events
    ADD CONSTRAINT alert_events_budget_id_fkey FOREIGN KEY (budget_id) REFERENCES public.budgets(id) ON DELETE CASCADE;


--
-- Name: alert_events alert_events_threshold_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.alert_events
    ADD CONSTRAINT alert_events_threshold_id_fkey FOREIGN KEY (threshold_id) REFERENCES public.budget_thresholds(id) ON DELETE SET NULL;


--
-- Name: budget_thresholds budget_thresholds_budget_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.budget_thresholds
    ADD CONSTRAINT budget_thresholds_budget_id_fkey FOREIGN KEY (budget_id) REFERENCES public.budgets(id) ON DELETE CASCADE;


--
-- Name: budget_thresholds budget_thresholds_notification_channel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.budget_thresholds
    ADD CONSTRAINT budget_thresholds_notification_channel_id_fkey FOREIGN KEY (notification_channel_id) REFERENCES public.notification_channels(id) ON DELETE SET NULL;


--
-- Name: budgets budgets_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.budgets
    ADD CONSTRAINT budgets_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: notification_channels notification_channels_owner_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.notification_channels
    ADD CONSTRAINT notification_channels_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: notification_deliveries notification_deliveries_channel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.notification_deliveries
    ADD CONSTRAINT notification_deliveries_channel_id_fkey FOREIGN KEY (channel_id) REFERENCES public.notification_channels(id) ON DELETE CASCADE;


--
-- Name: user_sessions user_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cloudcost
--

ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

