<script>
  // The newer builder's class page (play/characters/build/classes/<id>) in DDB's markup: backdrop and figure,
  // gold border, tagline and badges, "How it feels to play", starting features, "Iconic Gear" and the subclass
  // cards. DDB's own texts come from extract_class_details.py where we have them (cls.ddbDetail); otherwise
  // the page shows the rules data: level-1 features, the PHB starting equipment and the subclass list.
  import Tagged from "../lib/Tagged.svelte";
  import { ddb, useStyles } from "../lib/ddb.svelte.js";
  import { book } from "../lib/format.js";

  let { cls, onselect, onback, blocked = "" } = $props();
  $effect(() => useStyles(["class-detail.css", "species-cards.css"]));

  const assets = window.DND5E.ddb;
  const detail = $derived(cls.ddbDetail || null);
  const icon = (key) => ddb.icons[key] || "";
  const firstSentence = (entries) => {
    const text = (entries || []).find((e) => typeof e === "string") || "";
    return text.split(/(?<=\.)\s/)[0];
  };
  const features = $derived(detail?.features?.length ? detail.features
    : cls.features.filter((f) => f.level === 1 && !f.variant).map((f) => ({ name: f.name, text: firstSentence(f.entries), tagged: true })));
  const gear = $derived(detail?.gear?.length ? detail.gear.map((g) => ({ text: g, tagged: true })) : (cls.startingEquipment?.default || []).map((g) => ({ text: g, tagged: true })));
  const subclasses = $derived(cls.subclasses.map((s) => ({ ...s, tagline: s.ddbTagline || "" })));
  // DDB titles subclasses "The / Archfey": a leading article becomes the small eyebrow line
  const split = (name) => (name.match(/^(The|Path of the|College of|Circle of the|Circle of|Oath of the|Oath of|Way of the|Way of|School of)\s+(.*)$/) || [null, "", name]).slice(1);
  const source = (b) => `${book(b)}${b === "phb" ? " (2014)" : ""}`.replace(/'/g, "’");
  const accent = $derived(detail?.color || "#c53131");
</script>

{#snippet selectButton(extra)}
  <button type="button" class="Button-module__EPiRJW__baseButton Button-module__EPiRJW__primary Button-module__EPiRJW__medium Button-module__EPiRJW__doubleArrow styles-module__oQuihG__selectButton {extra}"
    aria-disabled={!!blocked} disabled={!!blocked} aria-label="Select {cls.name}" onclick={onselect}>
    <span class="Button-module__EPiRJW__capContainer Button-module__EPiRJW__left">{@html icon("cd-cap-left-0")}</span>
    <span class="Button-module__EPiRJW__content">Select</span>
    <span class="Button-module__EPiRJW__capContainer Button-module__EPiRJW__right">{@html icon("cd-cap-right-0")}</span>
  </button>
{/snippet}

{#snippet filigree(position)}
  <div class="styles-module__zfee_G__filigreeDivider styles-module__zfee_G__alignBottom styles-module__0u7Fdq__filigreeDivider styles-module__fl6YuG__{position}" style="--fill: var(--color-gold-base);">
    {@html icon("cd-filigree-0")}{@html icon("cd-filigree-1")}{@html icon("cd-filigree-2")}{@html icon("cd-filigree-3")}{@html icon("cd-filigree-4")}
  </div>
{/snippet}

<div class="ddb-new-builder ddb-class-detail">
  <button type="button" class="ddb-class-detail-back" onclick={onback}>&larr; Back to classes</button>
  <div class="styles-module__MHRkpa__detailViewLayout" style="--background-color: #1b1d1f; --background-image: url({assets}/{cls.ddbHero});">
    <div class="styles-module__MHRkpa__wideScreenBackground"></div>
    <section class="styles-module__oQuihG__detailView styles-module__AD-FeG__detailPageContent pages-module__kXd57W__page styles-module__AD-FeG__desktopView"
      style="--theme-color: #1b1d1f; --accent-color: {accent}; --background-url: url({assets}/{cls.ddbHero}); --foreground-url: url({assets}/{cls.ddbFigure});">
      <div class="styles-module__oQuihG__foregroundImage"></div>
      <div class="styles-module__oQuihG__contentWrapper">
        <div class="styles-module__oQuihG__gradientContainer"></div>
        <div class="styles-module__oQuihG__borderContainer">
          <div class="styles-module__oQuihG__topBorderSvgs">{@html icon("cd-top-0")}<div class="styles-module__oQuihG__repeatContainer">{@html icon("cd-top-1")}</div>{@html icon("cd-top-2")}</div>
          <div class="styles-module__oQuihG__sideBorderSvgs">{@html icon("cd-side-0")}{@html icon("cd-side-1")}</div>
          <div class="styles-module__oQuihG__bottomBorderSvgs">{@html icon("cd-bottom-0")}<div class="styles-module__oQuihG__repeatContainer">{@html icon("cd-bottom-1")}</div>{@html icon("cd-bottom-2")}</div>
        </div>
        <div class="styles-module__oQuihG__content">
          <div class="styles-module__oQuihG__contentTop">
            {#if cls.ddbArt}<img alt="" class="styles-module__oQuihG__classIcon" src="{assets}/{cls.ddbArt}" />{/if}
            {@render selectButton("styles-module__oQuihG__desktop")}
          </div>
          <div class="styles-module__oQuihG__contentHeading">
            <span class="styles-module__oQuihG__sourceName">{source(cls.book)}</span>
            <h1 class="styles-module__oQuihG__title">{cls.name}</h1>
            {#if detail?.tagline}<p class="styles-module__oQuihG__tagline">{detail.tagline}</p>{/if}
            {#if detail?.badges?.length}
              <div class="styles-module__LS0KTq__badgesContainer">
                {#each detail.badges as badge}<div class="Badge-module__txXWja__container styles-module__LS0KTq__badge" style="background-color: color-mix(in srgb, #1b1d1f, transparent); border-color: {accent}; color: var(--lexicon_badge--text--default);"><span>{badge}</span></div>{/each}
              </div>
            {/if}
            {#if blocked}<p class="ddb-card-blocked-reason">{blocked}</p>{/if}
          </div>
          <div class="styles-module__oQuihG__classInfo">
            {#if detail?.feels?.length}
              <div><p class="styles-module__zQU0aW__eyebrow">Class Highlights</p><h2 class="styles-module__zQU0aW__title">How it feels to play</h2>
                <div class="styles-module__zQU0aW__description"><div class="styles-module__EfttyG__htmlContent"><ul>{#each detail.feels as line}<li>{line}</li>{/each}</ul></div></div></div>
            {/if}
            <div><p class="styles-module__zQU0aW__eyebrow">Starting Class Features</p><h2 class="styles-module__zQU0aW__title">What are their abilities?</h2>
              <div class="styles-module__zQU0aW__description"><ul class="styles-module__oQuihG__startingFeaturesList">
                {#each features as f}<li><span class="TextLink-module__j7mhJq__baseTextLink TextLink-module__j7mhJq__capitalized">{f.name}</span>: <span>{#if f.tagged}<Tagged text={f.text} />{:else}{f.text}{/if}</span></li>{/each}
              </ul></div></div>
          </div>
          <div class="styles-module__fl6YuG__gearSection" style="--accent-color: {accent};">
            {@render filigree("top")}
            <div class="styles-module__fl6YuG__gearContent">
              {#if cls.ddbGear}<div class="styles-module__fl6YuG__gearImageWrapper"><img alt="" class="styles-module__fl6YuG__gearImage" src="{assets}/{cls.ddbGear}" /></div>{/if}
              <div class="styles-module__fl6YuG__gearBulletedList"><p class="styles-module__zQU0aW__eyebrow">{detail?.gear?.length ? "Iconic Gear" : "Starting Equipment"}</p><h2 class="styles-module__zQU0aW__title">What equipment do they carry?</h2>
                <div class="styles-module__zQU0aW__description"><div class="styles-module__EfttyG__htmlContent"><ul>{#each gear as g}<li>{#if g.tagged}<Tagged text={g.text} />{:else}{g.text}{/if}</li>{/each}</ul></div></div></div>
            </div>
            {@render filigree("bottom")}
          </div>
          <div class="styles-module__jjeeRW__subCardSection">
            <p class="styles-module__jjeeRW__eyebrow">Subclass Options</p>
            <h2 class="styles-module__jjeeRW__title">What type of {cls.name} will you be?</h2>
            <div class="styles-module__tmzXDW__cardList styles-module__tmzXDW__sm styles-module__jjeeRW__subCardList"><div class="styles-module__tmzXDW__cards">
              {#each subclasses as sub (sub.id)}
                {@const [eyebrow, title] = split(sub.name)}
                <div class="styles-module__PzKZ2G__subCard" style="--desktop-background-url: url({assets}/img/source/ddb-newbuilder-texture-dark.2xzwcuzv5-rrs.png); --mobile-background-url: url({assets}/img/source/ddb-newbuilder-texture-dark.2xzwcuzv5-rrs.png);">
                  <div class="styles-module__PzKZ2G__backgroundImageContainer"><div class="styles-module__PzKZ2G__backgroundImage"></div></div>
                  <div class="styles-module__PzKZ2G__gradient"></div>
                  <div class="styles-module__PzKZ2G__contentWrapper"><div class="styles-module__PzKZ2G__mainContent">
                    <h3 class="styles-module__PzKZ2G__title">{#if eyebrow}<span class="styles-module__PzKZ2G__eyebrow">{eyebrow}</span>{/if}{title}</h3>
                    {#if sub.tagline}<p class="styles-module__PzKZ2G__description">{sub.tagline}</p>{/if}
                    <div class="styles-module__PzKZ2G__footer"><p class="styles-module__PzKZ2G__sourceName">{source(sub.book)}</p></div>
                  </div></div>
                </div>
              {/each}
            </div></div>
          </div>
        </div>
      </div>
    </section>
  </div>
</div>
