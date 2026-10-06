using System;
using System.Data;
using System.Configuration;
using System.Collections;
using System.Web;
using System.Web.Security;
using System.Web.UI;
using System.Web.UI.WebControls;
using System.Web.UI.WebControls.WebParts;
using System.Web.UI.HtmlControls;
using System.Data.SqlClient;
using EBS.Classes;
using EBS_Common.Classes.Misc;
using EBS_Common.Classes;
using System.Collections.Generic;

public partial class Quality_And_Safety_frmLagging_Indicators_Hdr : System.Web.UI.Page
{
    # region User defined variables
    DataSet Ds;
    SqlDataAdapter Da;
    SqlConnection Conn;
    public DataTable DtLagging_Indicators = new DataTable();
    string strConString = "";
    string ErrorString = "";
    Button[] btnEnableDisable;
    Int16 intMenu_id;
    Int32 intUser_Id;

    #endregion

    protected void Page_Load(object sender, EventArgs e)
    {

        # region Code to Enable / Disable Button
        #region Adding buttons which needs to pass
        var list = new List<Button>();
        list.Add(btnAdd);
        list.Add(btnUpdate);
        list.Add(btnSearch);
        //list.Add(btnPrint);
        btnEnableDisable = list.ToArray();
        #endregion

        strConString = ConfigurationManager.ConnectionStrings["provider_default"].ToString();

        #region 1st Parameter is always Menu Id
        string strScramble = Request.QueryString["A"];
        string strdeCrypt = clsMiscellaneous.decryptQueryString(strScramble.Replace(" ", "+"));
        intMenu_id = Convert.ToInt16(strdeCrypt);
        intUser_Id = Convert.ToInt16(Session["User_Id"].ToString());
        # endregion

        if (!IsPostBack)
        {
            EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString,"Add");
        }
        #endregion


        #region To fetch values from shp.Rig_Site_Mapping

        /// Fetch values from the selected record and populate the controls.
        if (tbPostbackFlag_Hidden.Value == "SEARCH")
        {
            Get_Data_For_Edit();
            tbPostbackFlag_Hidden.Value = "";
            EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString, "Search");
        }

        #endregion

        tbRig.Focus();
    }

    private void InsertUpdateData(EBS_Common.Classes.InsertUpdateData_Enum Type)
    {
        clsLagging_Indicators_Hdr _ObjMaster = new clsLagging_Indicators_Hdr(strConString);

        switch (Type)
        {
            case EBS_Common.Classes.InsertUpdateData_Enum.Insert:
                {
                    _ObjMaster.Company_Id = Convert.ToInt16(tbCompany_Id_Hidden.Value);
                    _ObjMaster.Rig_Id = Convert.ToInt16(tbRig_Id_Hidden.Value);
                    _ObjMaster.Report_No = tbReport_No.Text;
                    _ObjMaster.Period = "01/" + tbPeriod.Text;

                    _ObjMaster.Cr_User_Id = Convert.ToInt16(Session["User_Id"].ToString());
                    _ObjMaster.InsertMe();


                    break;
                }

            case EBS_Common.Classes.InsertUpdateData_Enum.Update:
                {                    
                    
                    _ObjMaster.Lagging_Indicator_Id = Convert.ToInt16(tbLagging_Indicator_Id_Hidden.Value);
                    Get_Lagging_Indicators_Dtl();

                    _ObjMaster.Mod_User_Id = Convert.ToInt16(Session["User_Id"].ToString());
                    _ObjMaster.UpdateMe(DtLagging_Indicators);
                    break;
                }
        }
        if ((_ObjMaster.ErrorString != "") && (_ObjMaster.ErrorString != null))
        {
            ErrorString = _ObjMaster.ErrorString;
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", _ObjMaster.ErrorString);
            return;
        }

        string strPopUp_Message = "";

        if (Type.ToString() == "Insert")
        {
            strPopUp_Message = "Saved";
        }
        else if (Type.ToString() == "Update")
        {
            strPopUp_Message = "Updated";            
        }
        else if (Type.ToString() == "Delete")
        {
            strPopUp_Message = "Deleted";
        }

        ScriptManager.RegisterStartupScript(this, this.GetType(), "MSG1", "<script>callpopup_ipwidth('Record " + strPopUp_Message + "', 2000,'',220);</script>", false);

        ClearMe(true);

        if (Type.ToString() == "Insert")
        {
            ClearMe(false);


            #region  Again Fill the containts
            tbLagging_Indicator_Id_Hidden.Value = Convert.ToString(_ObjMaster.Lagging_Indicator_Id);
            Get_Data_For_Edit();
            #endregion
        }
         

    }

    /// <summary>
    /// To clear the text boxes, default selection of combos.
    /// </summary>
    /// <param name="blnClearMainId">Whether to clear Main Id.</param>

    private void ClearMe(bool blnClearMainId)
    {
        /// Clear the hidden textboxes.

        if (blnClearMainId == true)
        {
            tbLagging_Indicator_Id_Hidden.Value = "";
           
        }
         
        #region Header Controls
        /// Clear Hidden controls.
        
        tbRig_Id_Hidden.Value = "";

        /// Clear other controls.
        
        tbRig.Text = "";
        tbReport_No.Text = "";
        tbPeriod.Text = "";
       
        #endregion Header Controls

        #region Assign default Values
        tbCompany_Id_Hidden.Value = "10";
        tbCompany_Name.Text = "OGD Services Limited";
        #endregion

        #region To set default css and enable the Header Controls
        ibtnRig_Id.Visible = true;
        ibtnCompany.Visible = true;

        tbReport_No.CssClass = "textbox";
        tbPeriod.CssClass = "textbox";

        tbReport_No.Attributes.Remove("OnKeyDown");
        tbPeriod.Attributes.Remove("OnKeyDown");
        #endregion

        #region Detail Controls
        /// Clear Hidden controls.   
        //tbLagging_Indicator_Dtl_Id_Hidden.Value = "";
        //tbIndicator_Type_Id_Hidden.Value = "";
        //tbIndicator_Subtype_Id_Hidden.Value = "";

        /// Clear other controls.
 
        grdLagging_Indicators.DataSource = "";
        grdLagging_Indicators.DataBind();
        grdLagging_Indicators.SelectedIndex = -1;
        #endregion

        #region To set default css and enable the Detail Controls

        #endregion
        EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString, "Clear");
    }

    protected void btnAdd_Click(object sender, EventArgs e)
    {
        InsertUpdateData(EBS_Common.Classes.InsertUpdateData_Enum.Insert);

        //after error it should not go in UPDATE MODE
        if (ErrorString == "")
        {
            EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString, "Search");
        }
    }

    protected void Get_Data_For_Edit()
    {
        ClearMe(false);
        Conn = new SqlConnection(strConString);
        try
        {

            if (Conn.State == ConnectionState.Closed)
                Conn.Open();

            Ds = new DataSet();
            Da = new SqlDataAdapter(OI.Def + "Prc_Lagging_Indicators_Hdr", Conn);
            Da.SelectCommand.CommandType = CommandType.StoredProcedure;

            Da.SelectCommand.Parameters.Add("@Lagging_Indicator_Id", SqlDbType.SmallInt).Value = Convert.ToInt16(tbLagging_Indicator_Id_Hidden.Value);
            Da.SelectCommand.Parameters.Add("@Prj_Cutoff_Date", System.Data.SqlDbType.Date).Value = Convert.ToDateTime(DateTime.ParseExact(ConfigurationManager.ConnectionStrings["Prj_Cutoff_Date"].ToString(), "dd/MM/yyyy", null));
    
        
            Da.SelectCommand.Parameters.Add("@Record_Status", SqlDbType.VarChar).Value = "Select";

            Da.Fill(Ds, "Data_For_Edit");

            #region Assign values to the Header controls
            tbCompany_Name.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Company_Name"].ToString();
            tbCompany_Id_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Company_Id"].ToString();

            tbRig.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Rig_Name"].ToString();
            tbRig_Id_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Rig_Id"].ToString();

            tbReport_No.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Report_No"].ToString();
            tbPeriod.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Period"].ToString();
            #endregion

            #region To disable Header controls and change the css
            tbReport_No.CssClass = "textbox_readonly";
            tbReport_No.Attributes.Add("OnKeyDown", "return RejectInput()");

            tbPeriod.CssClass = "textbox_readonly";
            tbPeriod.Attributes.Add("OnKeyDown", "return RejectInput()");

            ibtnRig_Id.Visible = false;
            ibtnCompany.Visible = false;
            #endregion

            #region Assign values to the Detail controls
            grdLagging_Indicators.DataSource = Ds.Tables["Data_For_Edit1"];
            grdLagging_Indicators.DataBind();    

            #endregion

        }
        catch (SqlException sqlexep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        catch (Exception exep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        finally
        {
            if (Conn.State == ConnectionState.Open)
            {
                Conn.Close();
                //Conn.Dispose();
            }
        }
    }

    protected void btnClear_Click(object sender, EventArgs e)
    {
        ClearMe(true);
    }

    protected void btnUpdate_Click(object sender, EventArgs e)
    {
        InsertUpdateData(EBS_Common.Classes.InsertUpdateData_Enum.Update);
    }

    protected void grdLagging_Indicators_RowDataBound(object sender, GridViewRowEventArgs e)
    {
        if (e.Row.RowType == DataControlRowType.DataRow)
        {
            HtmlInputHidden tbData_Change_Id_Hidden = (HtmlInputHidden)e.Row.FindControl("tbData_Change_Id_Hidden");

            TextBox tbTotal_Count = (TextBox)e.Row.FindControl("tbTotal_Count");
            TextBox tbActive = (TextBox)e.Row.FindControl("tbActive");        


            tbTotal_Count.Attributes.Add("onblur", "return Data_Change(" + tbData_Change_Id_Hidden.ClientID + ",'Y'," + tbTotal_Count.ClientID + ");");            
            tbActive.Attributes.Add("onblur", "return Data_Change(" + tbData_Change_Id_Hidden.ClientID + ",'N'," + tbData_Change_Id_Hidden.ClientID + ");");
        }
    }


    protected void Get_Lagging_Indicators_Dtl()
    {
        DtLagging_Indicators.Columns.Clear();
        DtLagging_Indicators.Rows.Clear();

        DtLagging_Indicators.Columns.Add("Lagging_Indicator_Dtl_Id");
        DtLagging_Indicators.Columns.Add("Total_Count");       
        DtLagging_Indicators.Columns.Add("Active");

        foreach (GridViewRow grdRow in grdLagging_Indicators.Rows)
        {
            HtmlInputHidden tbData_Change_Id_Hidden = (HtmlInputHidden)grdRow.FindControl("tbData_Change_Id_Hidden");

            if (tbData_Change_Id_Hidden.Value == "Y")
            {

                HtmlInputHidden tbLagging_Indicator_Dtl_Id_Hidden = (HtmlInputHidden)grdRow.FindControl("tbLagging_Indicator_Dtl_Id_Hidden");
                TextBox tbTotal_Count = (TextBox)grdRow.FindControl("tbTotal_Count");
                TextBox tbActive = (TextBox)grdRow.FindControl("tbActive");
                
                DataRow drRow;
                drRow = DtLagging_Indicators.NewRow();

                drRow["Lagging_Indicator_Dtl_Id"] = tbLagging_Indicator_Dtl_Id_Hidden.Value;

                if (tbTotal_Count.Text.Trim() != "")
                    drRow["Total_Count"] = tbTotal_Count.Text.Trim();
                else
                    drRow["Total_Count"] = null;

                drRow["Active"] = tbActive.Text;
                 
                DtLagging_Indicators.Rows.Add(drRow);

            }


        }
    }

}
