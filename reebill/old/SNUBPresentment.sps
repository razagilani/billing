<?xml version="1.0" encoding="UTF-8"?>
<structure version="9" htmlmode="strict" relativeto="*SPS" encodinghtml="UTF-8" encodingrtf="ISO-8859-1" encodingpdf="UTF-8" useimportschema="1" embed-images="1">
	<parameters/>
	<schemasources>
		<namespaces>
			<nspair prefix="sb" uri="skylinebill"/>
			<nspair prefix="ub" uri="utilitybill"/>
		</namespaces>
		<schemasources>
			<xsdschemasource name="XML" main="1" schemafile="C:\workspace-skyline\billing\UtilityBill.xsd" workingxmlfile="C:\workspace-skyline\billing\sample\Skyline-PECO-9443-01819-2009100609.xml">
				<xmltablesupport/>
				<textstateicons/>
			</xsdschemasource>
		</schemasources>
	</schemasources>
	<modules>
		<module spsfile="BillPresentment.sps"/>
		<module spsfile="SkylineBill.sps"/>
	</modules>
	<flags>
		<scripts/>
		<globalparts/>
		<designfragments/>
		<pagelayouts/>
	</flags>
	<scripts>
		<script language="javascript"/>
	</scripts>
	<importedxslt/>
	<globalstyles/>
	<mainparts>
		<children>
			<globaltemplate subtype="main" match="/">
				<children>
					<documentsection>
						<properties columncount="1" columngap="0.50in" headerfooterheight="fixed" pagemultiplepages="0" pagenumberingformat="1" pagenumberingstartat="auto" pagestart="next" paperheight="11in" papermarginbottom="0.79in" papermarginfooter="0.30in" papermarginheader="0.30in" papermarginleft="0.60in" papermarginright="0.60in" papermargintop="0.79in" paperwidth="8.50in"/>
					</documentsection>
					<template subtype="source" match="XML">
						<children>
							<newline/>
							<paragraph paragraphtag="h1">
								<children>
									<text fixtext="Skyline Normalized Utility Bill (SNUB)"/>
								</children>
							</paragraph>
							<paragraph>
								<properties align="right"/>
								<children>
									<text fixtext="SNUB  "/>
									<template subtype="element" match="ub:utilitybill">
										<children>
											<template subtype="attribute" match="id">
												<children>
													<content/>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
							</paragraph>
							<line/>
							<paragraph>
								<children>
									<paragraph paragraphtag="h2">
										<children>
											<text fixtext="Customer Account Records"/>
										</children>
									</paragraph>
									<paragraph paragraphtag="p">
										<children>
											<text fixtext="Customer Utility Account Number "/>
											<template subtype="element" match="ub:utilitybill">
												<children>
													<template subtype="element" match="ub:car">
														<children>
															<template subtype="element" match="ub:accountnumber">
																<children>
																	<content/>
																</children>
																<variables/>
															</template>
														</children>
														<variables/>
													</template>
												</children>
												<variables/>
											</template>
										</children>
									</paragraph>
									<tgrid>
										<properties border="0" width="100%"/>
										<children>
											<tgridbody-cols>
												<children>
													<tgridcol/>
													<tgridcol/>
												</children>
											</tgridbody-cols>
											<tgridbody-rows>
												<children>
													<tgridrow>
														<children>
															<tgridcell>
																<children>
																	<paragraph paragraphtag="h3">
																		<children>
																			<text fixtext="Billing Address"/>
																		</children>
																	</paragraph>
																	<tgrid>
																		<properties border="0"/>
																		<children>
																			<tgridbody-cols>
																				<children>
																					<template subtype="element" match="ub:utilitybill">
																						<children>
																							<template subtype="element" match="ub:car">
																								<children>
																									<template subtype="element" match="ub:billingaddress">
																										<children>
																											<tgridcol/>
																										</children>
																										<variables/>
																									</template>
																								</children>
																								<variables/>
																							</template>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridbody-cols>
																			<tgridbody-rows>
																				<children>
																					<tgridrow>
																						<children>
																							<tgridcell>
																								<children>
																									<template subtype="element" match="ub:addressee">
																										<children>
																											<content/>
																										</children>
																										<variables/>
																									</template>
																									<text fixtext="   "/>
																									<template subtype="element" match="ub:telephonenumber">
																										<children>
																											<content/>
																										</children>
																										<variables/>
																									</template>
																								</children>
																							</tgridcell>
																						</children>
																					</tgridrow>
																					<tgridrow>
																						<children>
																							<tgridcell>
																								<children>
																									<template subtype="element" match="ub:street">
																										<children>
																											<content/>
																										</children>
																										<variables/>
																									</template>
																								</children>
																							</tgridcell>
																						</children>
																					</tgridrow>
																					<tgridrow>
																						<children>
																							<tgridcell>
																								<children>
																									<template subtype="element" match="ub:city">
																										<children>
																											<content/>
																										</children>
																										<variables/>
																									</template>
																									<text fixtext="  "/>
																									<template subtype="element" match="ub:state">
																										<children>
																											<content/>
																										</children>
																										<variables/>
																									</template>
																									<text fixtext="  "/>
																									<template subtype="element" match="ub:country">
																										<children>
																											<content/>
																										</children>
																										<variables/>
																									</template>
																									<text fixtext="   "/>
																									<template subtype="element" match="ub:postalcode">
																										<children>
																											<content/>
																										</children>
																										<variables/>
																									</template>
																								</children>
																							</tgridcell>
																						</children>
																					</tgridrow>
																				</children>
																			</tgridbody-rows>
																		</children>
																	</tgrid>
																</children>
															</tgridcell>
															<tgridcell>
																<children>
																	<paragraph paragraphtag="h3">
																		<children>
																			<text fixtext="Service Address"/>
																		</children>
																	</paragraph>
																	<tgrid>
																		<properties border="0"/>
																		<children>
																			<tgridbody-cols>
																				<children>
																					<template subtype="element" match="ub:utilitybill">
																						<children>
																							<template subtype="element" match="ub:car">
																								<children>
																									<template subtype="element" match="ub:serviceaddress">
																										<children>
																											<tgridcol/>
																										</children>
																										<variables/>
																									</template>
																								</children>
																								<variables/>
																							</template>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridbody-cols>
																			<tgridbody-rows>
																				<children>
																					<tgridrow>
																						<children>
																							<tgridcell>
																								<children>
																									<template subtype="element" match="ub:addressee">
																										<children>
																											<content/>
																										</children>
																										<variables/>
																									</template>
																									<text fixtext="   "/>
																									<template subtype="element" match="ub:telephonenumber">
																										<children>
																											<content/>
																										</children>
																										<variables/>
																									</template>
																								</children>
																							</tgridcell>
																						</children>
																					</tgridrow>
																					<tgridrow>
																						<children>
																							<tgridcell>
																								<children>
																									<template subtype="element" match="ub:street">
																										<children>
																											<content/>
																										</children>
																										<variables/>
																									</template>
																								</children>
																							</tgridcell>
																						</children>
																					</tgridrow>
																					<tgridrow>
																						<children>
																							<tgridcell>
																								<children>
																									<template subtype="element" match="ub:city">
																										<children>
																											<content/>
																										</children>
																										<variables/>
																									</template>
																									<text fixtext="   "/>
																									<template subtype="element" match="ub:state">
																										<children>
																											<content/>
																										</children>
																										<variables/>
																									</template>
																									<text fixtext="   "/>
																									<template subtype="element" match="ub:country">
																										<children>
																											<content/>
																										</children>
																										<variables/>
																									</template>
																									<text fixtext="   "/>
																									<template subtype="element" match="ub:postalcode">
																										<children>
																											<content/>
																										</children>
																										<variables/>
																									</template>
																								</children>
																							</tgridcell>
																						</children>
																					</tgridrow>
																				</children>
																			</tgridbody-rows>
																		</children>
																	</tgrid>
																</children>
															</tgridcell>
														</children>
													</tgridrow>
												</children>
											</tgridbody-rows>
										</children>
									</tgrid>
								</children>
							</paragraph>
							<newline/>
							<line/>
							<newline/>
							<paragraph>
								<children>
									<paragraph paragraphtag="h2">
										<children>
											<text fixtext="Charge Summary"/>
										</children>
									</paragraph>
									<paragraph paragraphtag="p">
										<children>
											<text fixtext="Period From "/>
											<template subtype="element" match="ub:utilitybill">
												<children>
													<template subtype="element" match="ub:summary">
														<children>
															<template subtype="element" match="ub:billperiodbegin">
																<children>
																	<content>
																		<format datatype="date"/>
																	</content>
																</children>
																<variables/>
															</template>
														</children>
														<variables/>
													</template>
												</children>
												<variables/>
											</template>
											<text fixtext=" To "/>
											<template subtype="element" match="ub:utilitybill">
												<children>
													<template subtype="element" match="ub:summary">
														<children>
															<template subtype="element" match="ub:billperiodend">
																<children>
																	<content>
																		<format datatype="date"/>
																	</content>
																</children>
																<variables/>
															</template>
														</children>
														<variables/>
													</template>
												</children>
												<variables/>
											</template>
											<text fixtext="  Bill Issued "/>
											<template subtype="element" match="ub:utilitybill">
												<children>
													<template subtype="element" match="ub:summary">
														<children>
															<template subtype="element" match="ub:issuedate">
																<children>
																	<content>
																		<format datatype="date"/>
																	</content>
																</children>
																<variables/>
															</template>
														</children>
														<variables/>
													</template>
												</children>
												<variables/>
											</template>
											<text fixtext="  Due: "/>
											<template subtype="element" match="ub:utilitybill">
												<children>
													<template subtype="element" match="ub:summary">
														<children>
															<template subtype="element" match="ub:duedate">
																<children>
																	<content>
																		<format datatype="date"/>
																	</content>
																</children>
																<variables/>
															</template>
														</children>
														<variables/>
													</template>
												</children>
												<variables/>
											</template>
										</children>
									</paragraph>
									<paragraph paragraphtag="h3">
										<children>
											<text fixtext="Charges"/>
										</children>
									</paragraph>
									<tgrid>
										<properties border="0" width="100%"/>
										<children>
											<tgridbody-cols>
												<children>
													<tgridcol/>
													<tgridcol>
														<properties align="right"/>
													</tgridcol>
												</children>
											</tgridbody-cols>
											<tgridbody-rows>
												<children>
													<tgridrow>
														<children>
															<tgridcell>
																<children>
																	<text fixtext="Prior Balance"/>
																</children>
															</tgridcell>
															<tgridcell>
																<children>
																	<template subtype="element" match="ub:utilitybill">
																		<children>
																			<template subtype="element" match="ub:summary">
																				<children>
																					<template subtype="element" match="ub:priorbalance">
																						<children>
																							<content>
																								<format datatype="decimal"/>
																							</content>
																						</children>
																						<variables/>
																					</template>
																				</children>
																				<variables/>
																			</template>
																		</children>
																		<variables/>
																	</template>
																</children>
															</tgridcell>
														</children>
													</tgridrow>
													<tgridrow>
														<children>
															<tgridcell>
																<children>
																	<text fixtext="Previous Payments"/>
																</children>
															</tgridcell>
															<tgridcell>
																<children>
																	<tgrid>
																		<properties border="0"/>
																		<children>
																			<tgridbody-cols>
																				<children>
																					<tgridcol/>
																				</children>
																			</tgridbody-cols>
																			<tgridbody-rows>
																				<children>
																					<template subtype="element" match="ub:utilitybill">
																						<children>
																							<template subtype="element" match="ub:summary">
																								<children>
																									<template subtype="element" match="ub:previouspayment">
																										<children>
																											<tgridrow>
																												<children>
																													<tgridcell>
																														<children>
																															<template subtype="element" match="ub:amount">
																																<children>
																																	<content>
																																		<format datatype="decimal"/>
																																	</content>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																												</children>
																											</tgridrow>
																										</children>
																										<variables/>
																									</template>
																								</children>
																								<variables/>
																							</template>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridbody-rows>
																		</children>
																	</tgrid>
																</children>
															</tgridcell>
														</children>
													</tgridrow>
													<tgridrow>
														<children>
															<tgridcell>
																<children>
																	<text fixtext="Adjustments"/>
																</children>
															</tgridcell>
															<tgridcell>
																<children>
																	<tgrid>
																		<properties border="0"/>
																		<children>
																			<tgridbody-cols>
																				<children>
																					<tgridcol/>
																				</children>
																			</tgridbody-cols>
																			<tgridbody-rows>
																				<children>
																					<template subtype="element" match="ub:utilitybill">
																						<children>
																							<template subtype="element" match="ub:summary">
																								<children>
																									<template subtype="element" match="ub:adjustment">
																										<children>
																											<tgridrow>
																												<children>
																													<tgridcell>
																														<children>
																															<template subtype="element" match="ub:amount">
																																<children>
																																	<content>
																																		<format datatype="decimal"/>
																																	</content>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																												</children>
																											</tgridrow>
																										</children>
																										<variables/>
																									</template>
																								</children>
																								<variables/>
																							</template>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridbody-rows>
																		</children>
																	</tgrid>
																</children>
															</tgridcell>
														</children>
													</tgridrow>
													<tgridrow>
														<children>
															<tgridcell>
																<children>
																	<text fixtext="Balance Forward"/>
																</children>
															</tgridcell>
															<tgridcell>
																<children>
																	<template subtype="element" match="ub:utilitybill">
																		<children>
																			<template subtype="element" match="ub:summary">
																				<children>
																					<template subtype="element" match="ub:balanceforward">
																						<children>
																							<content>
																								<format datatype="decimal"/>
																							</content>
																						</children>
																						<variables/>
																					</template>
																				</children>
																				<variables/>
																			</template>
																		</children>
																		<variables/>
																	</template>
																</children>
															</tgridcell>
														</children>
													</tgridrow>
													<tgridrow>
														<children>
															<tgridcell>
																<children>
																	<text fixtext="Current Charges"/>
																</children>
															</tgridcell>
															<tgridcell>
																<children>
																	<tgrid>
																		<properties border="0"/>
																		<children>
																			<tgridbody-cols>
																				<children>
																					<tgridcol/>
																					<tgridcol/>
																				</children>
																			</tgridbody-cols>
																			<tgridbody-rows>
																				<children>
																					<template subtype="element" match="ub:utilitybill">
																						<children>
																							<template subtype="element" match="ub:summary">
																								<children>
																									<template subtype="element" match="ub:currentcharges">
																										<children>
																											<tgridrow>
																												<children>
																													<tgridcell>
																														<children>
																															<template subtype="attribute" match="service">
																																<children>
																																	<content/>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																													<tgridcell>
																														<children>
																															<content/>
																														</children>
																													</tgridcell>
																												</children>
																											</tgridrow>
																										</children>
																										<variables/>
																									</template>
																								</children>
																								<variables/>
																							</template>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridbody-rows>
																		</children>
																	</tgrid>
																</children>
															</tgridcell>
														</children>
													</tgridrow>
													<tgridrow>
														<children>
															<tgridcell>
																<children>
																	<text fixtext="Total Due"/>
																</children>
															</tgridcell>
															<tgridcell>
																<children>
																	<template subtype="element" match="ub:utilitybill">
																		<children>
																			<template subtype="element" match="ub:summary">
																				<children>
																					<template subtype="element" match="ub:totaldue">
																						<children>
																							<content>
																								<format datatype="decimal"/>
																							</content>
																						</children>
																						<variables/>
																					</template>
																				</children>
																				<variables/>
																			</template>
																		</children>
																		<variables/>
																	</template>
																</children>
															</tgridcell>
														</children>
													</tgridrow>
												</children>
											</tgridbody-rows>
										</children>
									</tgrid>
									<newline/>
									<text fixtext=" Late Payment Penalty: "/>
									<template subtype="element" match="ub:utilitybill">
										<children>
											<template subtype="element" match="ub:summary">
												<children>
													<template subtype="element" match="ub:latepayment">
														<children>
															<template subtype="element" match="ub:penalty">
																<children>
																	<content/>
																</children>
																<variables/>
															</template>
														</children>
														<variables/>
													</template>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
									<text fixtext="Amount: "/>
									<template subtype="element" match="ub:utilitybill">
										<children>
											<template subtype="element" match="ub:summary">
												<children>
													<template subtype="element" match="ub:latepayment">
														<children>
															<template subtype="element" match="ub:amount">
																<children>
																	<content/>
																</children>
																<variables/>
															</template>
														</children>
														<variables/>
													</template>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
									<newline/>
								</children>
							</paragraph>
							<line/>
							<paragraph>
								<children>
									<paragraph paragraphtag="h2">
										<children>
											<text fixtext="Charge Details"/>
										</children>
									</paragraph>
									<tgrid>
										<properties border="0" width="100%"/>
										<children>
											<tgridbody-cols>
												<children>
													<tgridcol>
														<properties align="right"/>
													</tgridcol>
												</children>
											</tgridbody-cols>
											<tgridbody-rows>
												<children>
													<tgridrow>
														<children>
															<tgridcell>
																<children>
																	<tgrid>
																		<properties border="0" width="100%"/>
																		<children>
																			<tgridbody-cols>
																				<children>
																					<tgridcol>
																						<properties align="left"/>
																					</tgridcol>
																					<tgridcol>
																						<properties align="left"/>
																					</tgridcol>
																					<tgridcol>
																						<properties align="right"/>
																					</tgridcol>
																				</children>
																			</tgridbody-cols>
																			<tgridheader-rows>
																				<children>
																					<tgridrow>
																						<children>
																							<tgridcell>
																								<children>
																									<paragraph paragraphtag="h3">
																										<children>
																											<text fixtext="Service"/>
																										</children>
																									</paragraph>
																								</children>
																							</tgridcell>
																							<tgridcell>
																								<children>
																									<paragraph paragraphtag="h3">
																										<children>
																											<text fixtext="Rate Schedule"/>
																										</children>
																									</paragraph>
																								</children>
																							</tgridcell>
																							<tgridcell>
																								<children>
																									<tgrid>
																										<properties border="0" width="100%"/>
																										<children>
																											<tgridbody-cols>
																												<children>
																													<tgridcol>
																														<properties align="left" width="15%"/>
																													</tgridcol>
																													<tgridcol>
																														<properties align="left" width="35%"/>
																													</tgridcol>
																													<tgridcol>
																														<properties align="right" width="10%"/>
																													</tgridcol>
																													<tgridcol>
																														<properties align="left" width="5%"/>
																													</tgridcol>
																													<tgridcol>
																														<properties align="left" width="10%"/>
																													</tgridcol>
																													<tgridcol>
																														<properties align="left" width="5%"/>
																													</tgridcol>
																													<tgridcol>
																														<properties align="right" width="10%"/>
																													</tgridcol>
																													<tgridcol>
																														<properties width="10%"/>
																													</tgridcol>
																												</children>
																											</tgridbody-cols>
																											<tgridbody-rows>
																												<children>
																													<tgridrow>
																														<children>
																															<tgridcell>
																																<children>
																																	<paragraph paragraphtag="h3">
																																		<children>
																																			<text fixtext="Charge"/>
																																		</children>
																																	</paragraph>
																																</children>
																															</tgridcell>
																															<tgridcell>
																																<children>
																																	<paragraph paragraphtag="h3">
																																		<children>
																																			<text fixtext="Description"/>
																																		</children>
																																	</paragraph>
																																</children>
																															</tgridcell>
																															<tgridcell>
																																<children>
																																	<paragraph paragraphtag="h3">
																																		<children>
																																			<text fixtext="Quantity"/>
																																		</children>
																																	</paragraph>
																																</children>
																															</tgridcell>
																															<tgridcell/>
																															<tgridcell>
																																<children>
																																	<paragraph paragraphtag="h3">
																																		<children>
																																			<text fixtext="Rate"/>
																																		</children>
																																	</paragraph>
																																</children>
																															</tgridcell>
																															<tgridcell/>
																															<tgridcell>
																																<children>
																																	<paragraph paragraphtag="h3">
																																		<children>
																																			<text fixtext="Amount"/>
																																		</children>
																																	</paragraph>
																																</children>
																															</tgridcell>
																															<tgridcell/>
																														</children>
																													</tgridrow>
																												</children>
																											</tgridbody-rows>
																										</children>
																									</tgrid>
																								</children>
																							</tgridcell>
																						</children>
																					</tgridrow>
																				</children>
																			</tgridheader-rows>
																			<tgridbody-rows>
																				<children>
																					<template subtype="element" match="ub:utilitybill">
																						<children>
																							<template subtype="element" match="ub:details">
																								<children>
																									<tgridrow>
																										<properties valign="top"/>
																										<children>
																											<tgridcell>
																												<children>
																													<template subtype="attribute" match="service">
																														<children>
																															<content/>
																														</children>
																														<variables/>
																													</template>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<children>
																													<template subtype="element" match="ub:rateschedule">
																														<children>
																															<content/>
																														</children>
																														<variables/>
																													</template>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<children>
																													<tgrid>
																														<properties border="0" width="100%"/>
																														<children>
																															<tgridbody-cols>
																																<children>
																																	<tgridcol/>
																																</children>
																															</tgridbody-cols>
																															<tgridbody-rows>
																																<children>
																																	<tgridrow>
																																		<children>
																																			<tgridcell>
																																				<children>
																																					<tgrid>
																																						<properties border="0" width="100%"/>
																																						<children>
																																							<tgridbody-cols>
																																								<children>
																																									<tgridcol>
																																										<properties align="left" valign="top" width="15%"/>
																																									</tgridcol>
																																									<tgridcol>
																																										<properties align="right" width="85%"/>
																																									</tgridcol>
																																								</children>
																																							</tgridbody-cols>
																																							<tgridbody-rows>
																																								<children>
																																									<template subtype="element" match="ub:chargegroup">
																																										<children>
																																											<tgridrow>
																																												<children>
																																													<tgridcell>
																																														<children>
																																															<template subtype="attribute" match="type">
																																																<children>
																																																	<content/>
																																																</children>
																																																<variables/>
																																															</template>
																																														</children>
																																													</tgridcell>
																																													<tgridcell>
																																														<children>
																																															<tgrid>
																																																<properties border="0" width="100%"/>
																																																<children>
																																																	<tgridbody-cols>
																																																		<children>
																																																			<tgridcol/>
																																																		</children>
																																																	</tgridbody-cols>
																																																	<tgridbody-rows>
																																																		<children>
																																																			<tgridrow>
																																																				<children>
																																																					<tgridcell>
																																																						<children>
																																																							<tgrid>
																																																								<properties border="0" width="100%"/>
																																																								<children>
																																																									<tgridbody-cols>
																																																										<children>
																																																											<tgridcol>
																																																												<properties align="left" width="41.20%"/>
																																																											</tgridcol>
																																																											<tgridcol>
																																																												<properties align="right" width="11.76%"/>
																																																											</tgridcol>
																																																											<tgridcol>
																																																												<properties align="left" width="5.88%"/>
																																																											</tgridcol>
																																																											<tgridcol>
																																																												<properties align="right" width="11.76%"/>
																																																											</tgridcol>
																																																											<tgridcol>
																																																												<properties align="left" width="5.88%"/>
																																																											</tgridcol>
																																																											<tgridcol>
																																																												<properties align="right" width="11.76%"/>
																																																											</tgridcol>
																																																											<tgridcol>
																																																												<properties width="11.76%"/>
																																																											</tgridcol>
																																																										</children>
																																																									</tgridbody-cols>
																																																									<tgridbody-rows>
																																																										<children>
																																																											<template subtype="element" match="ub:charges">
																																																												<children>
																																																													<template subtype="element" match="ub:charge">
																																																														<children>
																																																															<tgridrow>
																																																																<children>
																																																																	<tgridcell>
																																																																		<children>
																																																																			<template subtype="element" match="ub:description">
																																																																				<children>
																																																																					<content/>
																																																																				</children>
																																																																				<variables/>
																																																																			</template>
																																																																		</children>
																																																																	</tgridcell>
																																																																	<tgridcell>
																																																																		<children>
																																																																			<template subtype="element" match="ub:quantity">
																																																																				<children>
																																																																					<content/>
																																																																				</children>
																																																																				<variables/>
																																																																			</template>
																																																																		</children>
																																																																	</tgridcell>
																																																																	<tgridcell>
																																																																		<children>
																																																																			<template subtype="element" match="ub:quantity">
																																																																				<children>
																																																																					<template subtype="attribute" match="units">
																																																																						<children>
																																																																							<content/>
																																																																						</children>
																																																																						<variables/>
																																																																					</template>
																																																																				</children>
																																																																				<variables/>
																																																																			</template>
																																																																		</children>
																																																																	</tgridcell>
																																																																	<tgridcell>
																																																																		<children>
																																																																			<template subtype="element" match="ub:rate">
																																																																				<children>
																																																																					<content/>
																																																																				</children>
																																																																				<variables/>
																																																																			</template>
																																																																		</children>
																																																																	</tgridcell>
																																																																	<tgridcell>
																																																																		<children>
																																																																			<template subtype="element" match="ub:rate">
																																																																				<children>
																																																																					<template subtype="attribute" match="units">
																																																																						<children>
																																																																							<content/>
																																																																						</children>
																																																																						<variables/>
																																																																					</template>
																																																																				</children>
																																																																				<variables/>
																																																																			</template>
																																																																		</children>
																																																																	</tgridcell>
																																																																	<tgridcell>
																																																																		<properties align="right"/>
																																																																		<children>
																																																																			<template subtype="element" match="ub:total">
																																																																				<children>
																																																																					<content>
																																																																						<format datatype="decimal"/>
																																																																					</content>
																																																																				</children>
																																																																				<variables/>
																																																																			</template>
																																																																		</children>
																																																																	</tgridcell>
																																																																	<tgridcell/>
																																																																</children>
																																																															</tgridrow>
																																																														</children>
																																																														<variables/>
																																																													</template>
																																																												</children>
																																																												<variables/>
																																																											</template>
																																																										</children>
																																																									</tgridbody-rows>
																																																								</children>
																																																							</tgrid>
																																																						</children>
																																																					</tgridcell>
																																																				</children>
																																																			</tgridrow>
																																																			<tgridrow>
																																																				<children>
																																																					<tgridcell>
																																																						<children>
																																																							<line/>
																																																							<autocalc xpath="sum( charges/charge/total )">
																																																								<styles font-style="italic"/>
																																																							</autocalc>
																																																						</children>
																																																					</tgridcell>
																																																				</children>
																																																			</tgridrow>
																																																		</children>
																																																	</tgridbody-rows>
																																																</children>
																																															</tgrid>
																																														</children>
																																													</tgridcell>
																																												</children>
																																											</tgridrow>
																																										</children>
																																										<variables/>
																																									</template>
																																								</children>
																																							</tgridbody-rows>
																																						</children>
																																					</tgrid>
																																				</children>
																																			</tgridcell>
																																		</children>
																																	</tgridrow>
																																	<tgridrow>
																																		<children>
																																			<tgridcell>
																																				<children>
																																					<line/>
																																					<text fixtext=" "/>
																																					<autocalc xpath="sum( chargegroup/charges/charge/total )">
																																						<styles font-style="normal" font-weight="bold"/>
																																					</autocalc>
																																				</children>
																																			</tgridcell>
																																		</children>
																																	</tgridrow>
																																</children>
																															</tgridbody-rows>
																														</children>
																													</tgrid>
																												</children>
																											</tgridcell>
																										</children>
																									</tgridrow>
																								</children>
																								<variables/>
																							</template>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridbody-rows>
																		</children>
																	</tgrid>
																</children>
															</tgridcell>
														</children>
													</tgridrow>
												</children>
											</tgridbody-rows>
											<tgridfooter-rows>
												<children>
													<tgridrow>
														<children>
															<tgridcell>
																<children>
																	<text fixtext="Total charges "/>
																	<autocalc xpath="sum( utilitybill/details/chargegroup/charges/charge/total )">
																		<styles font-style="italic" font-weight="bold"/>
																	</autocalc>
																</children>
															</tgridcell>
														</children>
													</tgridrow>
												</children>
											</tgridfooter-rows>
										</children>
									</tgrid>
									<newline/>
								</children>
							</paragraph>
							<line/>
							<newline/>
							<paragraph>
								<children>
									<paragraph paragraphtag="h2">
										<children>
											<text fixtext="Billable Usage"/>
										</children>
									</paragraph>
									<tgrid>
										<properties align="right" border="0" width="100%"/>
										<children>
											<tgridbody-cols>
												<children>
													<tgridcol/>
													<tgridcol/>
													<tgridcol/>
													<tgridcol/>
												</children>
											</tgridbody-cols>
											<tgridheader-rows>
												<children>
													<tgridrow>
														<children>
															<tgridcell>
																<properties align="left"/>
																<children>
																	<paragraph paragraphtag="h3">
																		<children>
																			<text fixtext="Service"/>
																		</children>
																	</paragraph>
																</children>
															</tgridcell>
															<tgridcell>
																<properties align="left"/>
																<children>
																	<paragraph paragraphtag="h3">
																		<children>
																			<text fixtext="Rate Schedule"/>
																		</children>
																	</paragraph>
																</children>
															</tgridcell>
															<tgridcell>
																<children>
																	<tgrid>
																		<properties align="left" border="0" width="100%"/>
																		<children>
																			<tgridbody-cols>
																				<children>
																					<tgridcol/>
																					<tgridcol/>
																					<tgridcol/>
																				</children>
																			</tgridbody-cols>
																			<tgridbody-rows>
																				<children>
																					<tgridrow>
																						<children>
																							<tgridcell>
																								<properties align="left"/>
																								<children>
																									<paragraph paragraphtag="h3">
																										<children>
																											<text fixtext="Description"/>
																										</children>
																									</paragraph>
																								</children>
																							</tgridcell>
																							<tgridcell>
																								<properties align="left"/>
																								<children>
																									<paragraph paragraphtag="h3">
																										<children>
																											<text fixtext="Quantity"/>
																										</children>
																									</paragraph>
																								</children>
																							</tgridcell>
																							<tgridcell/>
																						</children>
																					</tgridrow>
																				</children>
																			</tgridbody-rows>
																		</children>
																	</tgrid>
																</children>
															</tgridcell>
															<tgridcell>
																<properties align="right"/>
																<children>
																	<paragraph paragraphtag="h3">
																		<children>
																			<text fixtext="Total"/>
																		</children>
																	</paragraph>
																</children>
															</tgridcell>
														</children>
													</tgridrow>
												</children>
											</tgridheader-rows>
											<tgridbody-rows>
												<children>
													<template subtype="element" match="ub:utilitybill">
														<children>
															<template subtype="element" match="ub:billableusage">
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<properties valign="top"/>
																				<children>
																					<template subtype="attribute" match="service">
																						<children>
																							<content/>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<properties valign="top"/>
																				<children>
																					<template subtype="element" match="ub:rateschedule">
																						<children>
																							<content/>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<tgrid>
																						<properties align="right" border="0" width="100%"/>
																						<children>
																							<tgridbody-cols>
																								<children>
																									<tgridcol/>
																									<tgridcol/>
																									<tgridcol/>
																								</children>
																							</tgridbody-cols>
																							<tgridbody-rows>
																								<children>
																									<template subtype="element" match="ub:usage">
																										<children>
																											<tgridrow>
																												<children>
																													<tgridcell>
																														<children>
																															<template subtype="element" match="ub:description">
																																<children>
																																	<content/>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																													<tgridcell>
																														<properties align="right"/>
																														<children>
																															<template subtype="element" match="ub:quantity">
																																<children>
																																	<content/>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																													<tgridcell>
																														<properties align="left"/>
																														<children>
																															<template subtype="element" match="ub:quantity">
																																<children>
																																	<template subtype="attribute" match="units">
																																		<children>
																																			<content/>
																																		</children>
																																		<variables/>
																																	</template>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																												</children>
																											</tgridrow>
																										</children>
																										<variables/>
																									</template>
																								</children>
																							</tgridbody-rows>
																						</children>
																					</tgrid>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<properties align="right"/>
																				<children>
																					<template subtype="element" match="ub:total">
																						<children>
																							<content/>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
																<variables/>
															</template>
														</children>
														<variables/>
													</template>
												</children>
											</tgridbody-rows>
										</children>
									</tgrid>
									<newline/>
									<newline/>
									<newline/>
									<newline/>
									<newline/>
									<newline/>
									<newline/>
								</children>
							</paragraph>
							<newline/>
							<line/>
							<newline/>
							<paragraph>
								<children>
									<paragraph paragraphtag="h2">
										<children>
											<text fixtext="Measured Usage"/>
										</children>
									</paragraph>
									<tgrid>
										<properties border="0" width="100%"/>
										<children>
											<tgridbody-cols>
												<children>
													<tgridcol>
														<properties align="left" valign="top" width="5%"/>
													</tgridcol>
													<tgridcol>
														<properties align="left" valign="top" width="7.5%"/>
													</tgridcol>
													<tgridcol>
														<properties align="left" valign="top" width="7.5%"/>
													</tgridcol>
													<tgridcol>
														<properties align="left" valign="top" width="7.5%"/>
													</tgridcol>
													<tgridcol>
														<properties align="left" valign="top" width="12.5%"/>
													</tgridcol>
													<tgridcol>
														<properties width="50%"/>
													</tgridcol>
													<tgridcol>
														<properties width="10%"/>
													</tgridcol>
												</children>
											</tgridbody-cols>
											<tgridheader-rows>
												<children>
													<tgridrow>
														<styles height="0.19in"/>
														<children>
															<tgridcell>
																<children>
																	<paragraph paragraphtag="h3">
																		<children>
																			<text fixtext="Est.?"/>
																		</children>
																	</paragraph>
																</children>
															</tgridcell>
															<tgridcell>
																<children>
																	<paragraph paragraphtag="h3">
																		<children>
																			<text fixtext="Prior Read"/>
																		</children>
																	</paragraph>
																</children>
															</tgridcell>
															<tgridcell>
																<children>
																	<paragraph paragraphtag="h3">
																		<children>
																			<text fixtext="Present Read"/>
																		</children>
																	</paragraph>
																</children>
															</tgridcell>
															<tgridcell>
																<children>
																	<paragraph paragraphtag="h3">
																		<children>
																			<text fixtext="Next Read"/>
																		</children>
																	</paragraph>
																</children>
															</tgridcell>
															<tgridcell>
																<children>
																	<paragraph paragraphtag="h3">
																		<children>
																			<text fixtext="Identifier"/>
																		</children>
																	</paragraph>
																</children>
															</tgridcell>
															<tgridcell>
																<children>
																	<tgrid>
																		<properties border="0" width="100%"/>
																		<children>
																			<tgridbody-cols>
																				<children>
																					<tgridcol>
																						<properties align="left" valign="top" width="25%"/>
																					</tgridcol>
																					<tgridcol>
																						<properties align="left" valign="top" width="25%"/>
																					</tgridcol>
																					<tgridcol>
																						<properties align="left" valign="top" width="10%"/>
																					</tgridcol>
																					<tgridcol>
																						<properties align="right" valign="top" width="12.5%"/>
																					</tgridcol>
																					<tgridcol>
																						<properties align="right" valign="top" width="12.5%"/>
																					</tgridcol>
																					<tgridcol>
																						<properties align="right" valign="top" width="5%"/>
																					</tgridcol>
																					<tgridcol>
																						<properties align="right" valign="top" width="20%"/>
																					</tgridcol>
																				</children>
																			</tgridbody-cols>
																			<tgridbody-rows>
																				<children>
																					<tgridrow>
																						<children>
																							<tgridcell>
																								<children>
																									<paragraph paragraphtag="h3">
																										<children>
																											<text fixtext="Register"/>
																										</children>
																									</paragraph>
																								</children>
																							</tgridcell>
																							<tgridcell>
																								<children>
																									<paragraph paragraphtag="h3">
																										<children>
																											<text fixtext="Description"/>
																										</children>
																									</paragraph>
																								</children>
																							</tgridcell>
																							<tgridcell>
																								<children>
																									<paragraph paragraphtag="h3">
																										<children>
																											<text fixtext="Units"/>
																										</children>
																									</paragraph>
																								</children>
																							</tgridcell>
																							<tgridcell>
																								<children>
																									<paragraph paragraphtag="h3">
																										<children>
																											<text fixtext="Prior"/>
																										</children>
																									</paragraph>
																								</children>
																							</tgridcell>
																							<tgridcell>
																								<children>
																									<paragraph paragraphtag="h3">
																										<children>
																											<text fixtext="Present"/>
																										</children>
																									</paragraph>
																								</children>
																							</tgridcell>
																							<tgridcell>
																								<children>
																									<paragraph paragraphtag="h3">
																										<children>
																											<text fixtext="Factor"/>
																										</children>
																									</paragraph>
																								</children>
																							</tgridcell>
																							<tgridcell>
																								<children>
																									<paragraph paragraphtag="h3">
																										<children>
																											<text fixtext="Total"/>
																										</children>
																									</paragraph>
																								</children>
																							</tgridcell>
																						</children>
																					</tgridrow>
																				</children>
																			</tgridbody-rows>
																		</children>
																	</tgrid>
																</children>
															</tgridcell>
															<tgridcell/>
														</children>
													</tgridrow>
												</children>
											</tgridheader-rows>
											<tgridbody-rows>
												<children>
													<template subtype="element" match="ub:utilitybill">
														<children>
															<template subtype="element" match="ub:measuredusage">
																<children>
																	<template subtype="element" match="ub:meter">
																		<children>
																			<tgridrow>
																				<children>
																					<tgridcell>
																						<children>
																							<template subtype="element" match="ub:estimated">
																								<children>
																									<content/>
																								</children>
																								<variables/>
																							</template>
																						</children>
																					</tgridcell>
																					<tgridcell>
																						<children>
																							<template subtype="element" match="ub:priorreaddate">
																								<children>
																									<content>
																										<format datatype="date"/>
																									</content>
																								</children>
																								<variables/>
																							</template>
																						</children>
																					</tgridcell>
																					<tgridcell>
																						<children>
																							<template subtype="element" match="ub:presentreaddate">
																								<children>
																									<content>
																										<format datatype="date"/>
																									</content>
																								</children>
																								<variables/>
																							</template>
																						</children>
																					</tgridcell>
																					<tgridcell>
																						<children>
																							<template subtype="element" match="ub:nextreaddate">
																								<children>
																									<content>
																										<format datatype="date"/>
																									</content>
																								</children>
																								<variables/>
																							</template>
																						</children>
																					</tgridcell>
																					<tgridcell>
																						<children>
																							<template subtype="element" match="ub:identifier">
																								<children>
																									<content/>
																								</children>
																								<variables/>
																							</template>
																						</children>
																					</tgridcell>
																					<tgridcell>
																						<children>
																							<tgrid>
																								<properties border="0" width="100%"/>
																								<children>
																									<tgridbody-cols>
																										<children>
																											<tgridcol>
																												<properties align="right"/>
																											</tgridcol>
																										</children>
																									</tgridbody-cols>
																									<tgridbody-rows>
																										<children>
																											<tgridrow>
																												<children>
																													<tgridcell>
																														<children>
																															<tgrid>
																																<properties border="0" width="100%"/>
																																<children>
																																	<tgridbody-cols>
																																		<children>
																																			<tgridcol>
																																				<properties align="left" width="25%"/>
																																			</tgridcol>
																																			<tgridcol>
																																				<properties align="left" width="25%"/>
																																			</tgridcol>
																																			<tgridcol>
																																				<properties align="left" width="10%"/>
																																			</tgridcol>
																																			<tgridcol>
																																				<properties align="right" width="12.5%"/>
																																			</tgridcol>
																																			<tgridcol>
																																				<properties align="right" width="12.5%"/>
																																			</tgridcol>
																																			<tgridcol>
																																				<properties align="right" width="5%"/>
																																			</tgridcol>
																																			<tgridcol>
																																				<properties align="right" width="20%"/>
																																			</tgridcol>
																																		</children>
																																	</tgridbody-cols>
																																	<tgridbody-rows>
																																		<children>
																																			<template subtype="element" match="ub:register">
																																				<children>
																																					<tgridrow>
																																						<children>
																																							<tgridcell>
																																								<children>
																																									<template subtype="element" match="ub:identifier">
																																										<children>
																																											<content/>
																																										</children>
																																										<variables/>
																																									</template>
																																								</children>
																																							</tgridcell>
																																							<tgridcell>
																																								<children>
																																									<template subtype="element" match="ub:description">
																																										<children>
																																											<content/>
																																										</children>
																																										<variables/>
																																									</template>
																																								</children>
																																							</tgridcell>
																																							<tgridcell>
																																								<children>
																																									<template subtype="element" match="ub:units">
																																										<children>
																																											<content/>
																																										</children>
																																										<variables/>
																																									</template>
																																								</children>
																																							</tgridcell>
																																							<tgridcell>
																																								<children>
																																									<template subtype="element" match="ub:priorreading">
																																										<children>
																																											<content>
																																												<format datatype="decimal"/>
																																											</content>
																																										</children>
																																										<variables/>
																																									</template>
																																								</children>
																																							</tgridcell>
																																							<tgridcell>
																																								<children>
																																									<template subtype="element" match="ub:presentreading">
																																										<children>
																																											<content>
																																												<format datatype="decimal"/>
																																											</content>
																																										</children>
																																										<variables/>
																																									</template>
																																								</children>
																																							</tgridcell>
																																							<tgridcell>
																																								<children>
																																									<template subtype="element" match="ub:factor">
																																										<children>
																																											<content>
																																												<format datatype="integer"/>
																																											</content>
																																										</children>
																																										<variables/>
																																									</template>
																																								</children>
																																							</tgridcell>
																																							<tgridcell>
																																								<children>
																																									<template subtype="element" match="ub:total">
																																										<children>
																																											<content>
																																												<format datatype="decimal"/>
																																											</content>
																																										</children>
																																										<variables/>
																																									</template>
																																								</children>
																																							</tgridcell>
																																						</children>
																																					</tgridrow>
																																				</children>
																																				<variables/>
																																			</template>
																																		</children>
																																	</tgridbody-rows>
																																</children>
																															</tgrid>
																														</children>
																													</tgridcell>
																												</children>
																											</tgridrow>
																										</children>
																									</tgridbody-rows>
																								</children>
																							</tgrid>
																						</children>
																					</tgridcell>
																					<tgridcell/>
																				</children>
																			</tgridrow>
																		</children>
																		<variables/>
																	</template>
																</children>
																<variables/>
															</template>
														</children>
														<variables/>
													</template>
												</children>
											</tgridbody-rows>
										</children>
									</tgrid>
									<newline/>
								</children>
							</paragraph>
							<line/>
							<condition>
								<children>
									<conditionbranch xpath="child::ub:utilitybill/ub:skylinemeasuredusage">
										<children>
											<paragraph>
												<children>
													<paragraph paragraphtag="h2">
														<children>
															<text fixtext="Skyline Measured Usage"/>
														</children>
													</paragraph>
												</children>
											</paragraph>
											<line/>
										</children>
									</conditionbranch>
								</children>
							</condition>
							<condition>
								<children>
									<conditionbranch xpath="child::utilitybill/usagehistory/usage">
										<children>
											<paragraph>
												<children>
													<paragraph paragraphtag="h2">
														<children>
															<text fixtext="Usage History"/>
														</children>
													</paragraph>
													<tgrid>
														<properties align="left" border="0" width="100%"/>
														<children>
															<tgridbody-cols>
																<children>
																	<tgridcol>
																		<properties align="left"/>
																	</tgridcol>
																	<tgridcol>
																		<properties align="left"/>
																	</tgridcol>
																	<tgridcol/>
																	<tgridcol>
																		<properties align="left"/>
																	</tgridcol>
																</children>
															</tgridbody-cols>
															<tgridheader-rows>
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<children>
																					<paragraph paragraphtag="h3">
																						<children>
																							<text fixtext="Date"/>
																						</children>
																					</paragraph>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<paragraph paragraphtag="h3">
																						<children>
																							<text fixtext="Days"/>
																						</children>
																					</paragraph>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<tgrid>
																						<properties border="0" width="100%"/>
																						<children>
																							<tgridbody-cols>
																								<children>
																									<tgridcol>
																										<properties align="left"/>
																									</tgridcol>
																									<tgridcol>
																										<properties align="left"/>
																									</tgridcol>
																									<tgridcol>
																										<properties align="left"/>
																									</tgridcol>
																								</children>
																							</tgridbody-cols>
																							<tgridbody-rows>
																								<children>
																									<tgridrow>
																										<children>
																											<tgridcell>
																												<children>
																													<paragraph paragraphtag="h3">
																														<children>
																															<text fixtext="Identifier"/>
																														</children>
																													</paragraph>
																												</children>
																											</tgridcell>
																											<tgridcell>
																												<children>
																													<paragraph paragraphtag="h3">
																														<children>
																															<text fixtext="Amount"/>
																														</children>
																													</paragraph>
																												</children>
																											</tgridcell>
																											<tgridcell/>
																										</children>
																									</tgridrow>
																								</children>
																							</tgridbody-rows>
																						</children>
																					</tgrid>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<paragraph paragraphtag="h3">
																						<children>
																							<text fixtext="Total"/>
																						</children>
																					</paragraph>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
															</tgridheader-rows>
															<tgridbody-rows>
																<children>
																	<template subtype="element" match="ub:utilitybill">
																		<children>
																			<template subtype="element" match="ub:usagehistory">
																				<children>
																					<template subtype="element" match="ub:usage">
																						<children>
																							<tgridrow>
																								<children>
																									<tgridcell>
																										<children>
																											<template subtype="element" match="ub:date">
																												<children>
																													<content>
																														<format datatype="date"/>
																													</content>
																												</children>
																												<variables/>
																											</template>
																										</children>
																									</tgridcell>
																									<tgridcell>
																										<children>
																											<template subtype="element" match="ub:days">
																												<children>
																													<content>
																														<format datatype="integer"/>
																													</content>
																												</children>
																												<variables/>
																											</template>
																										</children>
																									</tgridcell>
																									<tgridcell>
																										<children>
																											<template subtype="element" match="ub:register">
																												<children>
																													<tgrid>
																														<properties border="0" width="100%"/>
																														<children>
																															<tgridbody-cols>
																																<children>
																																	<tgridcol>
																																		<properties align="left"/>
																																	</tgridcol>
																																	<tgridcol>
																																		<properties align="right"/>
																																	</tgridcol>
																																	<tgridcol>
																																		<properties align="left"/>
																																	</tgridcol>
																																</children>
																															</tgridbody-cols>
																															<tgridbody-rows>
																																<children>
																																	<tgridrow>
																																		<children>
																																			<tgridcell>
																																				<children>
																																					<template subtype="element" match="ub:identifier">
																																						<children>
																																							<content/>
																																						</children>
																																						<variables/>
																																					</template>
																																				</children>
																																			</tgridcell>
																																			<tgridcell>
																																				<children>
																																					<template subtype="element" match="ub:total">
																																						<children>
																																							<content/>
																																						</children>
																																						<variables/>
																																					</template>
																																				</children>
																																			</tgridcell>
																																			<tgridcell>
																																				<children>
																																					<template subtype="element" match="ub:total">
																																						<children>
																																							<template subtype="attribute" match="units">
																																								<children>
																																									<content/>
																																								</children>
																																								<variables/>
																																							</template>
																																						</children>
																																						<variables/>
																																					</template>
																																				</children>
																																			</tgridcell>
																																		</children>
																																	</tgridrow>
																																</children>
																															</tgridbody-rows>
																														</children>
																													</tgrid>
																												</children>
																												<variables/>
																											</template>
																										</children>
																									</tgridcell>
																									<tgridcell>
																										<children>
																											<template subtype="element" match="ub:total">
																												<children>
																													<content/>
																												</children>
																												<variables/>
																											</template>
																										</children>
																									</tgridcell>
																								</children>
																							</tgridrow>
																						</children>
																						<variables/>
																					</template>
																				</children>
																				<variables/>
																			</template>
																		</children>
																		<variables/>
																	</template>
																</children>
															</tgridbody-rows>
														</children>
													</tgrid>
													<newline/>
												</children>
											</paragraph>
										</children>
									</conditionbranch>
								</children>
							</condition>
						</children>
						<variables/>
					</template>
				</children>
			</globaltemplate>
		</children>
	</mainparts>
	<globalparts/>
	<pagelayout>
		<properties paperheight="11.69in" paperwidth="8.27in"/>
	</pagelayout>
	<designfragments/>
</structure>
